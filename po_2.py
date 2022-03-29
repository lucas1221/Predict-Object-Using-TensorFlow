# -*- coding: utf-8 -*-
"""PO-2.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/15sYZ5mwQ5qoR3rgyVce92kSA0d1BKFd5

**bibliotecas**
"""

import json
import torchvision
import torch
import torch.nn as nn
import torchvision.transforms as T
import os
import xml.etree.ElementTree as ET
from PIL import Image,ImageDraw
from IPython.display import display
from torchvision.models.detection import FasterRCNN
from torchvision.models.detection.rpn import AnchorGenerator
import numpy as np

from google.colab import drive
drive.mount('/content/drive')

# Commented out IPython magic to ensure Python compatibility.
os.chdir('/content/drive/My Drive/Data')
import sys
sys.path.append('/content/drive/MyDrive/Data/mapeval.py')
# %load mapeval.py
from mapeval import voc_eval

with open('labels.json') as json_file:
    data = json.load(json_file)
    print(data)

"""Importacão dos **dados**"""

i=0
for h in data:
    if 'objects' in h['Label']:
        file_url = h['Labeled Data']
        file_name = h['External ID']
        objects = h['Label']['objects']
        boxes = []
        labels = []
        for obj in objects:
            labels.append(obj['value'])
            x1 = int(obj['bbox']['top'])
            y1 = int(obj['bbox']['left'])
            x2 = x1 + int(obj['bbox']['width'])
            y2 = y1 + int(obj['bbox']['height'])
            bbox  = [x1,y1,x2,y2]
            boxes.append(bbox)
        print(file_name,labels,boxes)
        i+=1
print(i)

"""**Dataset**



"""

class Dataset():
    def __init__(self,transforms = None):
        self.data = []
        self.transforms = transforms
        self.target_names = ['blanck']
        self.htarget_names = {'blanck':0}
        self.read_json()

    def get_label_id(self,name):
        if name not in self.htarget_names:
            self.htarget_names[name] = len(self.target_names)
            self.target_names.append(name)
        return self.htarget_names[name]
        
    def read_json(self):
        with open('labels.json') as json_file:
            data = json.load(json_file)
            for h in data:
                if 'objects' in h['Label']:
                    file_url = h['Labeled Data']
                    file_name = 'imagens'+os.sep+h['External ID']
                    objects = h['Label']['objects']
                    boxes = []
                    labels = []
                    for obj in objects:
                        labels.append(self.get_label_id(obj['value']))
                        x1 = int(obj['bbox']['left'])
                        y1 = int(obj['bbox']['top'])
                        x2 = x1 + int(obj['bbox']['width'])
                        y2 = y1 + int(obj['bbox']['height'])
                        bbox  = [x1,y1,x2,y2]
                        boxes.append(bbox)
                    h = {}
                    h['file_img'] = file_name
                    h['labels'] = labels
                    h['boxes']  = boxes
                    self.data.append(h)
    def __getitem__(self,i):
        img   = Image.open(self.data[i]['file_img']).convert("RGB")
        boxes = torch.tensor(self.data[i]['boxes'])
        if self.transforms != None:
            img,boxes = self.transforms(img,boxes)
        r = dict()
        r['boxes']   = boxes
        r['labels']  = torch.tensor(self.data[i]['labels'])
        return img,r
    def __len__(self):
        return len(self.data)

"""Tratamento de imagem"""

def resize(img,boxes,size):
    w, h = img.size
    ow, oh = size
    sw = float(ow) / w
    sh = float(oh) / h
    img = img.resize((ow,oh), Image.BILINEAR)
    boxes = boxes * torch.tensor([sw,sh,sw,sh])
    return img, boxes

size = (300,300)
def transform_data(img,boxes):
    img,boxes = resize(img,boxes,size)
    img = T.Compose([
          T.ToTensor(), 
          T.Normalize((0.485,0.456,0.406),(0.229,0.224,0.225))          
    ])(img)
    return img,boxes

data = Dataset(transforms=transform_data)

"""Divisão dos conjuntos"""

n = len(data)
n_treino = int(0.7*n)
n_teste  = n-n_treino

n,n_treino,n_teste

ds_treino,ds_teste = torch.utils.data.random_split(data,(n_treino,n_teste))

def collate_fn(batch):
    return tuple(zip(*batch))
dl_treino = torch.utils.data.DataLoader(ds_treino,batch_size = 8,collate_fn=collate_fn)
dl_teste  = torch.utils.data.DataLoader(ds_teste,batch_size = 12,collate_fn=collate_fn)

imgs,targets = next(iter(dl_treino))

imgs

nview = Image.open(data.data[0]['file_img'])

data.data[0]['boxes']

idimg = 1
nview = T.ToPILImage()(imgs[idimg]*torch.Tensor([0.229,0.224,0.225]).view(3,1,1)+torch.Tensor([0.485,0.456,0.406]).view(3,1,1))

def draw_boxes(img,boxes,labels):
    imdraw = ImageDraw.Draw(img)
    for (box,label) in zip(boxes,labels):
        box = list(box)
        imdraw.rectangle(box,outline='red')
        text = "%d"%(label)
        imdraw.text((box[0],box[1]),text,fill='red')
    display(img)

draw_boxes(nview,targets[idimg]['boxes'],targets[idimg]['labels'])

model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=True)

in_features = model.roi_heads.box_predictor.cls_score.in_features
model.box_predictor = torchvision.models.detection.faster_rcnn.FastRCNNPredictor(in_features,3)

opt = torch.optim.SGD(model.parameters(), lr=0.01, momentum=0.9, weight_decay=0.0005)
lr_scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(opt)

device = torch.device('cuda:0') if torch.cuda.is_available() else torch.device('cpu')

torch.cuda.get_device_properties(0)

model.to(device)

def train(epoch):
    model.train()
    bloss=[]
    for images,targets in dl_treino:
        images = list(image.to(device) for image in images)
        targets = [{k:v.to(device) for k,v in t.items()} for t in targets]
        
        loss_dict = model(images,targets)
        losses = sum(loss for loss in loss_dict.values())
        
        opt.zero_grad()
        losses.backward()
        opt.step()
       
        for loss in loss_dict.keys():
            print("%.10s %4.3f"%(loss,loss_dict[loss].item()))
        print("Total Loss %4.3f\n"%(losses))
        bloss.append(losses.item())
    
    print("\nEPOCH %d LR %5.5f\n"%(epoch,opt.param_groups[0]['lr']))

def evaluate(epoch):
    model.eval()
    pred_boxes = []
    pred_labels = []
    pred_scores = []
    gt_boxes = []
    gt_labels = []
    lmap = []
    lap  = []
    with torch.no_grad():
        for images,targets in dl_teste:
            images = list(image.to(device) for image in images)
            pred   = model(images)
            for i in range(len(targets)):
                gt_boxes.append(targets[i]['boxes'])
                gt_labels.append(targets[i]['labels'])
                pred_boxes.append(pred[i]['boxes'].cpu())
                pred_labels.append(pred[i]['labels'].cpu())
                pred_scores.append(pred[i]['scores'].cpu())
                r = voc_eval(pred_boxes, pred_labels, pred_scores,
                gt_boxes, gt_labels)
                print(r)
                lmap.append(r['map'])
           
    print(np.mean(lmap))

    return np.mean(lmap)

best_map = 0.0

for epoch in range(100):
    train(epoch)
    map = evaluate(epoch)
    lr_scheduler.step(1.0-map)
    if map > best_map:
        best_map = map
        torch.save(model,'best_map_labelbox.pth')
        print('saving model')

nview = T.ToPILImage()(imgs[-2]*torch.Tensor([0.229,0.224,0.225]).view(3,1,1)+torch.Tensor([0.485,0.456,0.406]).view(3,1,1))

imgs[-1].shape

model.eval()

pred   = model(imgs[-2].view([1,3,300,300]).to(device))

pred

draw_boxes(nview,pred[0]['boxes'],pred[0]['labels'])

from IPython.display import clear_output
clear_output()