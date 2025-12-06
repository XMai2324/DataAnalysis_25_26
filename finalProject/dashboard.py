import requests
import bs4 as bs
import re


import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os

def read_all_csv(folder_path):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    folder_path = os.path.join(base_dir, folder_path)

    dataframes = {}
    for file in os.listdir(folder_path):
        if file.endswith(".csv"):
            file_path = os.path.join(folder_path, file)
            dataframes[file.replace(".csv", "")] = pd.read_csv(file_path)
            print(f"Đã đọc: {file}")
    return dataframes

dfs = read_all_csv("data")

