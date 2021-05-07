import torch
from torch import nn
from torch import optim
from torch.nn import functional as F
import math

class ConvNet(nn.Module):
    """
    Description
    """
    def __init__(self, n_classes=2):
        super(ConvNet, self).__init__()
        
        self.conv1 = nn.Conv2d(2, 16, kernel_size=5, padding = 3)
        self.conv2 = nn.Conv2d(16, 20, kernel_size=3, padding = 3)
        self.bn1 = nn.BatchNorm2d(16)
        self.bn2 = nn.BatchNorm2d(20)
        self.bn3 = nn.BatchNorm1d(720)
        self.fc1 = nn.Linear(720, 100)
        self.fc2 = nn.Linear(100, n_classes)
        
    def forward(self, x):
        """
        General structure of one layer:
            Input -> Convolution -> BatchNorm -> Activation(ReLu) -> Maxpooling -> Output
        """
        # 1st layer 
        x = F.max_pool2d(F.relu(self.bn1(self.conv1(x))), kernel_size=2)
        # 2nd layer 
        x = F.max_pool2d(F.relu(self.bn2(self.conv2(x))), kernel_size=2)
        # 3rd layer
        x = F.relu(self.fc1(self.bn3(x.view(x.size()[0], -1))))
        # 4th layer
        x = self.fc2(F.dropout(x)) 
        
        return x


# performs convolution on image with "in_channels" channels, returns 
# image of the same size with "filters" channels
class ConvBlock(nn.Module):

    def __init__(self, in_channels, filters=4, kernel_size=3):
        super(ConvBlock, self).__init__()
        self.filters = filters
        self.kernel_size = kernel_size
        self.conv = nn.Conv2d(in_channels, filters, kernel_size)
        self.bn = nn.BatchNorm2d(num_features=filters)

    def forward(self, x):
        padding = math.ceil(0.5 * (self.kernel_size - 1))
        pad = nn.ZeroPad2d(padding)    
        x = pad(x)   
        x = self.conv(x)
        x = self.bn(x)
        x = F.relu(x)
        return x

# block used to compute auxiliary loss
class AuxConvBlock(nn.Module):
    def __init__(self, n_classes, in_channels, filters=16, kernel_size=3):
        super(AuxConvBlock, self).__init__()
        self.conv_block = ConvBlock(in_channels, filters, kernel_size)
        self.avg_pool = nn.AvgPool2d(kernel_size=2) # img size goes from 14x14 to 7x7
        self.dense = nn.Linear(in_features = filters * 7 * 7, out_features=n_classes)

    def forward(self, x):
        x = self.conv_block(x)
        preds = self.avg_pool(x)
        preds = torch.flatten(preds, start_dim=1)
        preds = self.dense(preds)
        return x, preds



class DeepConvNet(nn.Module):

    def __init__(self, use_auxiliary_loss, depth=30, n_classes=2, filters=16, in_channels=2):
        super(DeepConvNet, self).__init__()
        if depth < 30 and use_auxiliary_loss:
            raise ValueError("Number of ConvBlocks must be greater or equal than 30 when using auziliary loss")
        self.depth = depth
        self.use_auxiliary_loss = use_auxiliary_loss
        self.filters = filters
        blocks = []
        blocks.append(ConvBlock(in_channels=in_channels, filters=filters, kernel_size=3))
        for i in range(1, self.depth):
            # every five conv blocks insert one block to apply auxiliary loss
            if use_auxiliary_loss and i % 5 == 0:
                block = AuxConvBlock(n_classes = in_channels*10, in_channels=filters, filters=filters, kernel_size=3)
            else:
                block = ConvBlock(in_channels=filters, filters=filters, kernel_size=3)
            blocks.append(block)
            blocks.append(ConvBlock(in_channels=filters, filters=filters, kernel_size=3))
        blocks.append(ConvBlock(in_channels=filters, filters=32, kernel_size=3))
        self.conv_blocks = nn.ModuleList(blocks)
        self.avg_pool = nn.AvgPool2d(kernel_size=14) #global average pooling
        self.dropout = nn.Dropout()
        self.dense = nn.Linear(in_features=32, out_features=n_classes)

    def forward(self, x):
        aux_preds = []
        for block in self.conv_blocks:
            if isinstance(block, AuxConvBlock):
                x, aux_pred = block(x)
                aux_preds.append(aux_pred)
            else:
                x = block(x)
        x = self.avg_pool(x)
        x = torch.flatten(x, start_dim=1)
        x = self.dropout(x)
        x = self.dense(x)   
        if self.use_auxiliary_loss:
            return x, aux_preds
        else:
            return x     

            

class MLP(nn.Module):
    """
    MLP with 4 layers
    """
    def __init__(self, n_classes=2):
        super(MLP, self).__init__()
        
        self.layers = nn.Sequential(
            nn.Linear(392, 350),
            nn.ReLU(),
            nn.Linear(350, 250),
            nn.ReLU(),
            nn.Linear(250, 200),
            nn.ReLU(),
            nn.Linear(200, 20),
            nn.ReLU(),
            nn.Linear(20, n_classes),
        )
        
    def forward(self, x):
        """
        General structure of one layer:
            Input -> Linear -> Activation(ReLu) -> Output
        """
        x = x.view(x.size(0), -1)
        x = self.layers(x)
        return x


class ResidualBlock(nn.Module):
    def __init__(self, filters, input_channels, conv_shortcut = False,  kernel_size=3, stride=1):
        super(ResidualBlock, self).__init__()
        self.stride = stride
        self.kernel_size = kernel_size
        self.filters = filters
        self.input_channels = input_channels
        self.conv_shortcut = conv_shortcut
        if self.conv_shortcut:
            self.conv_sc = nn.Conv2d(in_channels=input_channels, out_channels= 4*filters, kernel_size=1, stride=stride)
            self.bn_sc = nn.BatchNorm2d(num_features=4*filters)

        self.conv1 = nn.Conv2d(in_channels=input_channels, out_channels=filters, kernel_size=1, stride=stride)
        self.bn1 = nn.BatchNorm2d(num_features=filters)
    
        self.conv2 = nn.Conv2d(in_channels=filters, out_channels=filters, kernel_size=kernel_size, stride=stride)
        self.bn2 = nn.BatchNorm2d(num_features=filters)
        
        #conv3 keeps image size
        self.conv3 = nn.Conv2d(in_channels=filters, out_channels=4 * filters, kernel_size=1)
        self.bn3 = nn.BatchNorm2d(num_features=4*filters)
        
    def forward(self, x):
        if self.conv_shortcut:
            shortcut = self.bn_sc(self.conv_sc(x))
        else:
            shortcut = x
       # print("shortcut size:", shortcut.size())
        x = F.relu(self.bn1(self.conv1(x)))
       #print("after first convolution", x.size())
        padding = math.ceil(0.5 * (x.size()[2] * (self.stride - 1) + self.kernel_size - self.stride))
        #print(padding)
        pad = nn.ZeroPad2d(padding)
        x = pad(x)
        #print("after padding", x.size())
        x = F.relu(self.bn2(self.conv2(x)))
      #  print("after second convolution", x.size())
        x = self.bn3(self.conv3(x))
       # print("after third convolution", x.size())
        x = torch.add(x, shortcut)
        x = F.relu(x)
        return x
      


class ResNet(nn.Module):
    def __init__(self, depth, n_classes, input_channels=2, filters=32, input_size=14):
        super(ResNet, self).__init__()
        self.depth = depth
        self.input_channels = input_channels
        # residual blocks keep the channels with same size as input images
        blocks = []
        blocks.append(ResidualBlock(filters=filters, input_channels=2, conv_shortcut=True))
        for i in range(depth - 1):
            blocks.append(ResidualBlock(filters=filters, input_channels=4*filters))

        self.blocks = nn.ModuleList(blocks)
        self.avg_pool = nn.AvgPool2d(kernel_size=input_size) #global average pooling
        self.dropout = nn.Dropout()
        self.dense = nn.Linear(in_features=4*filters, out_features=n_classes)

    def forward(self, x):
        for block in self.blocks:
            x = block(x)

        x = self.avg_pool(x)
        x = torch.flatten(x, start_dim=1)
        x = self.dropout(x)
        x = self.dense(x)
        return x


class Siamese(nn.Module):
    def __init__(self, use_auxiliary_loss, filters=16):
        super(Siamese, self).__init__()
        self.auxiliary_loss = use_auxiliary_loss
        self.back_bone = DeepConvNet(use_auxiliary_loss, n_classes = 10, filters=filters, in_channels=1)
        self.dense = nn.Linear(in_features = 10, out_features=2)

    def forward(self, x):
        x1, x2 = torch.split(x, split_size_or_sections=[1,1], dim=1) # split channels
        if self.auxiliary_loss:
            x1, aux_preds1 = self.back_bone(x1)
            x2, aux_preds2 = self.back_bone(x2)
            x = torch.subtract(x1, x2)
            x = self.dense(x)
            aux_preds = []
            for aux_pred1, aux_pred2 in zip(aux_preds1, aux_preds2):
                aux_preds.append(torch.cat((aux_pred1, aux_pred2), dim=1))
            aux_preds.append(torch.cat((x1, x2), dim=1))
            return x, aux_preds
        else:
            x1 = self.back_bone(x1)
            x2 = self.back_bone(x2)
            x = torch.subtract(x1, x2)
            x = self.dense(x)
            return x






################################################################
# returns number of trainable parameters in the model
def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)



