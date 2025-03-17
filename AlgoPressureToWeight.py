import struct
import json
import numpy as np
import statistics
from collections import deque


class AlgoPressureToWeight:
    def __init__(self, sampleRate = 10, printData:bool = False, dbg:bool = True):
        self.dbg = dbg
        self.printData = printData
        self.inCalibration = False
        self.calib_target = 0
        self.std_dev = 0
        self.window_len = int(3 * sampleRate)
        if self.window_len < 30:
            self.window_len = 30
        self.thres = 2
        self.dataset_fit = []
        self.dataset_p = []
        self.timestamp_p = []
        self.dataset_t = []
        self.timestamp_t = []

    def updateCalibStatus(self, inCalibration:bool = False, calib_target:float = 0.0):
        if (not self.inCalibration) and inCalibration:
            self.dataset_p = []
            self.timestamp_p = []
            self.dataset_t = []
            self.timestamp_t = []
            self.sum_diff = 0

        self.inCalibration = inCalibration
        self.calib_target = calib_target

    def updateData(self, sensorType:str, val:float, timestmap_ms:int):
        if sensorType[0] == 'p':
            self.dataset_p.append(val)
            self.timestamp_p.append(timestmap_ms)
        elif sensorType[0] == 't':
            self.dataset_t.append(val)
            self.timestamp_t.append(timestmap_ms)
        else:
            return


        if self.inCalibration:
            if self.calib_target < 1e-6:
                #taring
                if len(self.dataset_p) >= self.window_len:
                    self.dataset_p = self.dataset_p[0 - self.window_len:]
                    self.std_dev = statistics.stdev(self.dataset_p)
                    if self.dbg:
                        print(f"stdev: {self.std_dev}")
            else:
                len_p = len(self.dataset_p)
                if len_p > 1:
                    diff = self.dataset_p[len_p - 1] - self.dataset_p[len_p - 2]
                    if diff > 3 * self.std_dev:
                        self.sum_diff += diff

