#!/bin/bash

#sudo su

cd $(cd $(dirname "$0") && pwd)

pip3 install -r requirements.txt

sudo python3 scpro.py
