from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from scipy.stats import ttest_ind
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler


# Green
green = "CryoSense.30aea42d5fa8"
red = "CryoSense.807d3ac2dde4"
cols = ["sensor.LIS2HH12.AcX", "sensor.LIS2HH12.AcY", "sensor.LIS2HH12.AcZ"]


# Format is timestamp,x,y,z
data1 = pd.read_csv('/tmp/green.csv')
data2 = pd.read_csv('/tmp/red.csv')

# Assuming the Unix timestamp is in seconds. If it's in milliseconds, replace 's' with 'ms'
data1['timestamp'] = pd.to_datetime(data1['timestamp'], unit='s')
data2['timestamp'] = pd.to_datetime(data2['timestamp'], unit='s')

# Set the timestamp column as the index
data1.set_index('timestamp', inplace=True)
data2.set_index('timestamp', inplace=True)

sample_width = '120s'
#sample_width = '900S'
sample_width = '3600S'
#sample_width = '86400S'
data1_resampled = data1.resample(sample_width).mean()
data2_resampled = data2.resample(sample_width).mean()

data1 = data1_resampled
data2 = data2_resampled

print("Resampled:")
print(data1_resampled)
print(data2_resampled)

# Calculate magnitude as a single measurement for each device
data1['magnitude'] = np.sqrt(data1['x']**2 + data1['y']**2 + data1['z']**2)
data2['magnitude'] = np.sqrt(data2['x']**2 + data2['y']**2 + data2['z']**2)

# Merge to ensure that we have overlapping data
data_merged = pd.merge(data1_resampled, data2_resampled, left_index=True, right_index=True, suffixes=('_1', '_2'))

key = "magnitude"
key = "x"
data_merged = data_merged.dropna(subset=['%s_1'%key, '%s_2'%key])
data_difference = abs(data_merged['%s_1'%key] - data_merged['%s_2'%key]) / data_merged['%s_1'%key]

fig, axs = plt.subplots(3)
single_day = datetime(2023, 6, 25)
next_day = single_day + timedelta(days=1)

axs[0].plot(data1_resampled)
axs[0].set_title("Green")
#axs[0].set_xlim([single_day, next_day])
axs[0].set_ylim([0, 0.3])

axs[1].plot(data2_resampled)
axs[1].set_title("Red")
#axs[1].set_xlim([single_day, next_day])
axs[1].set_ylim([0, 0.3])

axs[2].plot(data_difference)
axs[2].set_title("Relative diff, {}".format(key).title())
#axs[2].set_xlim([single_day, next_day])
#axs[2].set_ylim([-0.2, 0.2])

plt.tight_layout()
plt.show()

# Plot the difference array
#plt.plot(data_difference)
#plt.title("Difference between Green and Red Magnitude")
#plt.plot(data_difference)
#plt.title("Green and Red Magnitude")
#plt.show()

#data_difference = data1['magnitude'] - data2['magnitude']

print("Difference:", data_difference)

fraction_len = len(data_difference) // 2

print("Start: [:{}], end: [{}:]".format(fraction_len, -fraction_len))
start = data_difference[:fraction_len]
end = data_difference[-fraction_len:]

data_difference.to_csv("/tmp/diffs.csv")

t_stat, p_value = ttest_ind(start, end)

print(f'T-statistic: {t_stat}')
print(f'p-value: {p_value}')
