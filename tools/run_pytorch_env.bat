@echo off
chcp 65001 >nul
call E:\anaconda\Scripts\activate.bat E:\anaconda\envs\pytorch
python %*
