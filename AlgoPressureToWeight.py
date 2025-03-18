import struct
import json
import numpy as np
import statistics
from collections import deque
from datetime import datetime
#from sklearn.linear_model import LinearRegression
from scipy.stats import linregress



class AlgoPressureToWeight:
    def __init__(self, sampleRate = 10, printData:bool = False, dbg:bool = True):
        self.dbg = dbg
        self.printData = printData
        self.inCalibration = False
        self.calib_target = 0
        self.std_dev = 1.34
        self.window_len = int(3 * sampleRate)
        if self.window_len < 30:
            self.window_len = 30

        self.stddev_sample_sz = int (30 * sampleRate)
        if self.stddev_sample_sz < 30:
            self.stddev_sample_sz = 30

        self.thres_n = 3
        self.MAX_DATASET_LEN = 1000

        self.dataset_fit = []
        self.dataset_p = []
        self.meta_info_p = []
        self.dataset_t = []
        self.meta_info_t = []
        self.idx_start = -1
        self.idx_stop = -1
        self.sum_diff = 0

        self.model = None

        self.subscribers = []

    def updateCalibStatus(self, inCalibration:bool = False, calib_target:float = 0.0):
        if (not self.inCalibration) and inCalibration:
            self.dataset_p = []
            self.meta_info_p = []
            self.dataset_t = []
            self.meta_info_t = []
            self.sum_diff = 0

        self.inCalibration = inCalibration
        self.calib_target = calib_target

    def subscribe(self, cb):
        self.subscribers.append(cb)

    def __onWindowedEventStart(self):
        seq_start = self.meta_info_p[self.idx_start][1]
        seq_stop = seq_start
        if self.dbg:
            print(f"window event - start, {seq_start}, {seq_stop}, {self.sum_diff}, {self.inCalibration}, {self.calib_target}")
        pass
    def __onWindowedEventStop(self):
        seq_start = self.meta_info_p[self.idx_start][1]
        seq_stop = self.meta_info_p[self.idx_stop][1]
        if self.dbg:
            print(f"window event - stop, {seq_start}, {seq_stop}, {self.sum_diff}, {self.inCalibration}, {self.calib_target}")

        if self.sum_diff > 0:
            if self.inCalibration:
                    self.__updateDSFit()
            else:
                if self.model is not None:
                    data_in = [self.sum_diff]
                    weight = self.__predict(data_in)[0]
                    if self.dbg:
                        print(f"window event - stop, {seq_start}, {seq_stop}, {self.sum_diff}, {self.inCalibration}, {weight}")
                    for cb in self.subscribers:
                        cb(weight, self.meta_info_p[self.idx_stop][0])
        else:
            if self.inCalibration:
                pass
            else:
                pass

        self.idx_start = -1

    def __update_params_skl(self):
        data = self.dataset_fit
        x = np.array([item[0] for item in data]).reshape(-1, 1)  # Features (x)
        y = np.array([item[1] for item in data])  # Target (y)

        model = LinearRegression()
        self.model = model
        model.fit(x, y)

        y_pred = model.predict(x)

        r_squared = model.score(x, y)

        residuals = y - y_pred
        n = len(y)
        m = x.shape[1]
        std_error = np.sqrt(np.sum(residuals**2) / (n - m - 1))
        if self.dbg:
            print(f"R²: {r_squared}")
            print(f"Standard Error: {std_error}")
            print(f"Coefficient (slope): {model.coef_}")
            print(f"Intercept: {model.intercept_}")

    def __update_params_spy(self):
        data = self.dataset_fit
        x = np.array([item[0] for item in data])
        y = np.array([item[1] for item in data])
        self.model = (slope, intercept, r_value, p_value, std_err) = linregress(x, y)
        if self.dbg:
            print("Slope:", slope)
            print("Intercept:", intercept)
            print("R-squared:", r_value**2)
            print("Standard Error:", std_err)
    def __predict(self, data_in):
        data_out = [self.model[0] * xi + self.model[1] for xi in data_in]

        return data_out

    def __updateDSFit(self):
        vector = (self.sum_diff, self.calib_target)
        found = False
        for i in range(len(self.dataset_fit)):
            if (self.dataset_fit[i][1] == vector[1]):
                self.dataset_fit[i] = vector
                found = True
                break
        if not found:
            self.dataset_fit.append(vector)

        if self.dbg:
            print(f"data points so far:{len(self.dataset_fit)}")
        len_dps = len(self.dataset_fit)
        if len_dps >= 2:
            self.__update_params_spy()


    def updateData(self, sensorType:str, val:float, timestmap:datetime, seq:int = 0):
        meta_info = (timestmap, seq)
        if sensorType[0] == 'p':
            self.dataset_p.append(val)
            self.meta_info_p.append(meta_info)
            len_p = len(self.dataset_p)
            if len_p > self.MAX_DATASET_LEN:
                self.dataset_p = self.dataset_p[-self.MAX_DATASET_LEN:]
                len_p = len(self.dataset_p)
        elif sensorType[0] == 't':
            self.dataset_t.append(val)
            self.meta_info_t.append(meta_info)
            len_t = len(self.dataset_t)
            if len_t > self.MAX_DATASET_LEN:
                self.dataset_t = self.dataset_t[-self.MAX_DATASET_LEN:]
                len_t = len(self.dataset_t)
        else:
            return

        if self.inCalibration and self.calib_target < 1e-6:
            #taring
            if len_p >= self.stddev_sample_sz:
                dataset_p = self.dataset_p[0 - self.stddev_sample_sz:]
                self.std_dev = 0.8*self.std_dev + 0.2 * statistics.stdev(dataset_p)
                if self.dbg:
                    print(f"stdev: {self.std_dev}")
        else:
            if len_p > 1:
                diff = self.dataset_p[len_p - 1] - self.dataset_p[len_p - 2]
                if abs(diff) > self.thres_n * self.std_dev:
                    if -1 == self.idx_start:
                        self.idx_start = len_p - 1
                        self.sum_diff = diff
                        if self.dbg:
                            print(f"ev_start: {seq}, {val}, {self.thres_n * self.std_dev}")
                        self.__onWindowedEventStart()
                    else:
                        self.sum_diff += diff
                else:
                    if self.idx_start != -1:
                        self.idx_stop = len_p - 2
                        self.__onWindowedEventStop()

