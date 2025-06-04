import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from binance.client import Client
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import threading
import time
from datetime import datetime
from matplotlib.figure import Figure
from preferredsoundplayer import *

# Inicialización
client = Client(api_key='', api_secret='')
symbols = ['BTCUSDT', 'PEPEUSDT']
symbol_index = 0
current_view = 'main'

intervals = ['1m', '3m', '15m', '1h', '1d']
candles_needed = 100

# GUI Setup
root = tk.Tk()
root.title("Crypto Multi-Timeframe Analyzer")
root.geometry("1300x1000")

fig = None
canvas = None

button_frame = tk.Frame(root)
button_frame.pack(side="top", fill="x", pady=10)

view_options = ['main', 'analytical', 'floors']


def toggle_view():
    global current_view
    idx = view_options.index(current_view)
    current_view = view_options[(idx + 1) % len(view_options)]
    update_current_view()


def toggle_symbol():
    global symbol_index
    symbol_index = (symbol_index + 1) % len(symbols)
    update_current_view()


btn_toggle_view = tk.Button(button_frame, text="Cambiar Vista", command=toggle_view, height=2, width=20)
btn_toggle_view.pack(side="left", padx=20)

btn_toggle_symbol = tk.Button(button_frame, text="Cambiar Símbolo", command=toggle_symbol, height=2, width=20)
btn_toggle_symbol.pack(side="left", padx=20)

frame = tk.Frame(root)
frame.pack(fill="both", expand=True)


def get_data(interval):
    raw = client.get_klines(symbol=symbols[symbol_index], interval=interval, limit=candles_needed)
    df = pd.DataFrame(raw, columns=['timestamp','open','high','low','close','volume','close_time',
                                    'quote_asset_volume','number_of_trades','taker_buy_base',
                                    'taker_buy_quote','ignore'])
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df[['time', 'close', 'high', 'low']]

def check_last_3_candles_and_alert():
    df = get_data('3m')
    last3 = df[-3:]
    greens = [row['close'] > row['low'] for _, row in last3.iterrows()]
    if all(greens):
        try:
            playsound('/a.mp3')
        except Exception as e:
            print(f"Error al reproducir sonido: {e}")

def find_local_extrema(prices):
    maxima = []
    minima = []
    for i in range(1, len(prices) - 1):
        if prices[i] > prices[i - 1] and prices[i] > prices[i + 1]:
            maxima.append((i, prices[i]))
        if prices[i] < prices[i - 1] and prices[i] < prices[i + 1]:
            minima.append((i, prices[i]))
    return maxima[-3:], minima[-3:]


def plot_main_view():
    global fig, canvas

    if fig is None or canvas is None:
        fig = Figure(figsize=(12, 15))
        fig.subplots_adjust(hspace=0.6)
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.get_tk_widget().pack(fill="both", expand=True)
    else:
        fig.clear()

    axs = [fig.add_subplot(5, 1, i + 1) for i in range(5)]

    for i, interval in enumerate(intervals):
        df = get_data(interval)
        df['EMA9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['EMA21'] = df['close'].ewm(span=21, adjust=False).mean()
        recent = df[-50:].copy()

        x = np.arange(50).reshape(-1, 1)
        y = recent['close'].values.reshape(-1, 1)
        model = LinearRegression().fit(x, y)
        trend = model.predict(x).flatten()

        close = recent['close'].values
        time = recent['time']

        axs[i].plot(time, close, label='Precio')
        axs[i].plot(time, recent['EMA9'], label='EMA9', linestyle='--')
        axs[i].plot(time, recent['EMA21'], label='EMA21', linestyle='--')
        axs[i].plot(time, trend, label='Regresión Lineal 50', color='red')

        axs[i].fill_between(time, close, trend, where=close > trend, facecolor='green', alpha=0.3, interpolate=True)
        axs[i].fill_between(time, close, trend, where=close < trend, facecolor='red', alpha=0.3, interpolate=True)

        axs[i].set_title(f"{symbols[symbol_index]} - {interval}")
        axs[i].legend(loc='center left', bbox_to_anchor=(1, 0.5))
        axs[i].grid(True)

    canvas.draw()


def plot_analytical_view():
    global fig, canvas

    if fig is None or canvas is None:
        fig = Figure(figsize=(12, 10))
        fig.subplots_adjust(hspace=0.6)
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.get_tk_widget().pack(fill="both", expand=True)
    else:
        fig.clear()

    axs = [fig.add_subplot(2, 1, i + 1) for i in range(2)]
    targets = ['1m', '3m']

    for i, interval in enumerate(targets):
        df = get_data(interval)
        recent = df[-50:].copy()
        axs[i].plot(recent['time'], recent['close'], label='Precio')

        for count, color in zip([10, 20, 35, 50], ['orange', 'blue', 'green', 'red']):
            x = np.arange(count).reshape(-1, 1)
            y = recent['close'].values[:count].reshape(-1, 1)
            model = LinearRegression().fit(x, y)
            trend = model.predict(np.arange(count).reshape(-1, 1)).flatten()
            time_segment = recent['time'].values[:count]
            close_segment = recent['close'].values[:count]

            axs[i].plot(time_segment, trend, label=f'Reg {count} velas', color=color)

            if count == 50:
                axs[i].fill_between(time_segment, close_segment, trend, where=close_segment > trend,
                                    facecolor='green', alpha=0.3, interpolate=True)
                axs[i].fill_between(time_segment, close_segment, trend, where=close_segment < trend,
                                    facecolor='red', alpha=0.3, interpolate=True)

            if count < 50:
                trend_ext = model.predict(np.arange(50).reshape(-1, 1))[count:]
                axs[i].plot(recent['time'].values[count:], trend_ext, linestyle='dotted', color=color)

        axs[i].set_title(f"{symbols[symbol_index]} - {interval} (Análisis)")
        axs[i].legend(loc='center left', bbox_to_anchor=(1, 0.5))
        axs[i].grid(True)

    canvas.draw()


def plot_floors_view():
    global fig, canvas

    if fig is None or canvas is None:
        fig = Figure(figsize=(12, 10))
        fig.subplots_adjust(hspace=0.5)
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.get_tk_widget().pack(fill="both", expand=True)
    else:
        fig.clear()

    axs = [fig.add_subplot(3, 1, i + 1) for i in range(3)]
    targets = ['3m', '15m', '1h']

    for i, interval in enumerate(targets):
        df = get_data(interval)
        recent = df[-50:].copy()
        axs[i].plot(recent['time'], recent['close'], label='Precio')

        maxima, minima = find_local_extrema(recent['close'].values)

        for idx, val in maxima:
            axs[i].axhline(y=val, color='green', linestyle='--', linewidth=1)
        for idx, val in minima:
            axs[i].axhline(y=val, color='red', linestyle='--', linewidth=1)

        axs[i].set_title(f"{symbols[symbol_index]} - {interval} (Pisos y Techos)")
        axs[i].grid(True)

    canvas.draw()


def update_price_label():
    pass


def update_current_view():
    if current_view == 'main':
        plot_main_view()
    elif current_view == 'analytical':
        plot_analytical_view()
    else:
        plot_floors_view()
    update_price_label()


def update_loop():
    while True:
        time.sleep(60)
        root.after(0, update_current_view)
        root.after(0, lambda: [update_current_view(), check_last_3_candles_and_alert()])


update_current_view()
threading.Thread(target=update_loop, daemon=True).start()

root.mainloop()
