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
        self.weight_baseline = 0
        self.std_dev = 1.34
        self.window_len = int(3 * sampleRate)
        if self.window_len < 30:
            self.window_len = 30

        self.stddev_sample_sz = int (30 * sampleRate)
        if self.stddev_sample_sz < 30:
            self.stddev_sample_sz = 30

        self.MAX_DATASET_LEN = 200

        self.cfg = {
                "thres_n": 3,
                "settle_hold_dur": 15,
                "feather_p": (5, 14),
                "feather_n": (6, 3),
                "error_tor":0.10,   #10%
                "auto_tare": True,
        }
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
        self.last_weight = (0, 0)

    def updateCalibStatus(self, inCalibration:bool = False, calib_target:float = 0.0):
        if (not self.inCalibration) and inCalibration:
            self.dataset_p = []
            self.meta_info_p = []
            self.dataset_t = []
            self.meta_info_t = []
            self.idx_start = -1
            self.idx_stop = -1
            self.sum_diff = 0
            if self.calib_target < 1e-6:
                self.weight_baseline = 0

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
        if self.dbg:
            seq_start = self.meta_info_p[self.idx_start][1]
            seq_stop = self.meta_info_p[self.idx_stop][1]
            print(f"window event - stop, {seq_start}, {seq_stop}, {self.sum_diff}, {self.inCalibration}, {self.calib_target}")

        self.__adj_sel_window()

        weight = None
        if self.inCalibration:
            if self.sum_diff > 0:
                weight = self.calib_target
            else:
                weight = 0  #force to be zero
            self.__updateDSFit()
        else:
            if self.model is not None:
                data_in = [self.sum_diff]
                if self.sum_diff > 0:
                    weight = self.__predict(data_in)[0] + self.weight_baseline
                else:
                    if self.cfg["auto_tare"]:
                        if self.__isLastWeightRemoved():
                            weight = 0
                    if weight is None:
                        weight = self.__predict(data_in)[0] + self.weight_baseline
                if self.dbg:
                    print(f"window event - stop (predict), {seq_start}, {seq_stop}, {self.sum_diff}, {self.inCalibration}, {self.weight_baseline}, {weight}")
            elif self.sum_diff < 0:
                if self.__isLastWeightRemoved():
                    weight = 0

        self.last_weight = (self.sum_diff, weight)

        if weight is not None:
            for cb in self.subscribers:
                cb(weight, self.meta_info_p[self.idx_stop][0])
            self.weight_baseline = weight

        self.idx_start = -1

    def __adj_sel_window(self):
        if self.sum_diff > 0:
            idx_trigger = self.idx_start
            self.idx_start = idx_trigger - self.cfg["feather_p"][0]
            self.idx_stop = idx_trigger + self.cfg["feather_p"][1]
        else:
            idx_trigger = self.idx_start
            self.idx_start = idx_trigger - self.cfg["feather_n"][0]
            self.idx_stop = idx_trigger + self.cfg["feather_n"][1]
        if self.idx_start < 0:
            self.idx_start = 0
        if self.idx_stop >= len(self.dataset_p):
            self.idx_stop = -1

        if self.idx_start < 0:
            self.idx_start = 0

        seq_start = self.meta_info_p[self.idx_start][1]
        seq_stop = self.meta_info_p[self.idx_stop][1]
        self.sum_diff = self.dataset_p[self.idx_stop] - self.dataset_p[self.idx_start]
        if self.dbg:
            print(f"window event - stop adj, {seq_start}, {seq_stop}, {self.sum_diff}, {self.inCalibration}, {self.calib_target}")

    def __isLastWeightRemoved(self):
        if self.last_weight[0] > 0:
            delta = abs(abs(self.sum_diff) - self.last_weight[0])
            if (delta < self.cfg["error_tor"] * self.last_weight[0]):
                if self.dbg:
                    print(f"seems last weight removed")
                return True
        return False

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
        vector = (abs(self.sum_diff), self.calib_target)
        found = False
        for i in range(len(self.dataset_fit)):
            if (self.dataset_fit[i][1] == self.calib_target):
                fea_in = (abs(self.sum_diff) + self.dataset_fit[i][0]) * 0.5
                self.dataset_fit[i] = (fea_in, self.calib_target)
                found = True
                break
        if not found:
            self.dataset_fit.append(vector)

        if self.dbg:
            print(f"data points so far:{len(self.dataset_fit)}")
        len_dps = len(self.dataset_fit)
        if len_dps >= 2:
            self.__update_params_spy()

    def __truncDataBuf(self):
        len_p = len(self.dataset_p)
        if len_p > self.MAX_DATASET_LEN:
            headroom = 100
            if self.idx_start > headroom:
                start = self.idx_start - headroom
                self.idx_start = headroom
                self.dataset_p = self.dataset_p[start:]
                self.meta_info_p = self.meta_info_p[start:]
            else:
                pass

    def updateData(self, sensorType:str, val:float, timestmap:datetime, seq:int = 0):
        meta_info = (timestmap, seq)
        if sensorType[0] == 'p':
            self.dataset_p.append(val)
            self.meta_info_p.append(meta_info)
            self.__truncDataBuf()
        elif sensorType[0] == 't':
            self.dataset_t.append(val)
            self.meta_info_t.append(meta_info)
            len_t = len(self.dataset_t)
            if len_t > self.MAX_DATASET_LEN:
                self.dataset_t = self.dataset_t[-self.MAX_DATASET_LEN:]
                self.meta_info_t = self.meta_info_t[-self.MAX_DATASET_LEN:]
                len_t = len(self.dataset_t)
        else:
            return

        len_p = len(self.dataset_p)

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
                if abs(diff) > self.cfg["thres_n"] * self.std_dev:
                    self.settle_hold_cnt = 0
                    if -1 == self.idx_start:
                        self.idx_start = len_p - 1
                        self.idx_stop = len_p - 1
                        self.sum_diff = diff
                        if self.dbg:
                            print(f'ev_start: {seq}, {val}, {self.cfg["thres_n"] * self.std_dev}')
                        self.__onWindowedEventStart()
                    else:
                        self.sum_diff += diff
                else:
                    if -1 == self.idx_start:
                        pass
                    else:
                        self.settle_hold_cnt += 1
                        if self.settle_hold_cnt >= self.cfg["settle_hold_dur"]:
                            self.idx_stop = len_p - 1
                            self.__onWindowedEventStop()

