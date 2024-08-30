import serial
import csv
import os
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import threading
import numpy as np

# Ganti dengan port serial yang sesuai
serial_port = 'COM6'  # Ganti dengan port yang benar dari hasil list_ports
baud_rate = 9600
output_folder = os.path.dirname(os.path.abspath(__file__))
output_file = os.path.join(output_folder, "sink_databarufiks2.csv")

ser = serial.Serial(serial_port, baud_rate)

def save_data_to_file(data):
    file_exists = os.path.isfile(output_file)
    
    with open(output_file, 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        if not file_exists:
            csvwriter.writerow(["Round phase1", "Round phase2", "Node ID", "X Position", "Y Position", "Initial Energy", "Temperature", "Humidity", "Gas", "Voltage", "Cluster", "CH", "CH ID", "Throughput"])
        for row in data:
            csvwriter.writerow(row)
    print(f"Data berhasil disimpan ke file: {output_file}")

current_data = []
round_count = 0
capture_data = False
cluster_voltage = {}
cluster_throughput = {}
node_colors = {}
node_data = {}

# Warna untuk masing-masing cluster
colors = ['b', 'g', 'r']

# Grafik setup
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
plt.subplots_adjust(hspace=0.5)

def update_graph(frame):
    if len(cluster_voltage) == 0 or len(cluster_throughput) == 0:
        return
    
    ax1.clear()
    ax2.clear()
    
    ax1.set_title('Ronde vs Energi Residu per Cluster')
    ax1.set_xlabel('Ronde')
    ax1.set_ylabel('Energi Residu')
    
    ax2.set_title('Ronde vs Throughput per Cluster')
    ax2.set_xlabel('Ronde')
    ax2.set_ylabel('Throughput (Bytes/round)')
    
    for cluster_id in cluster_voltage.keys():
        rounds = sorted(cluster_voltage[cluster_id].keys())
        avg_voltages = [cluster_voltage[cluster_id][round] for round in rounds]
        total_throughputs = [cluster_throughput[cluster_id][round] for round in rounds]
        
        ax1.plot(rounds, avg_voltages, label=f'Cluster {cluster_id}', color=colors[cluster_id % len(colors)])
        ax2.plot(rounds, total_throughputs, label=f'Cluster {cluster_id}', color=colors[cluster_id % len(colors)])
    
    ax1.legend()
    ax2.legend()

def calculate_averages():
    global cluster_voltage, cluster_throughput
    
    cluster_voltage.clear()
    cluster_throughput.clear()
    
    for round_num, data in node_data.items():
        for cluster_id, nodes in data.items():
            voltages = [entry['voltage'] for node_entries in nodes.values() for entry in node_entries]
            throughputs = [entry['throughput'] for node_entries in nodes.values() for entry in node_entries]
            
            if len(voltages) > 0:
                avg_voltage = sum(voltages) / len(voltages)
                total_throughput = sum(throughputs)
                
                if cluster_id not in cluster_voltage:
                    cluster_voltage[cluster_id] = {}
                if cluster_id not in cluster_throughput:
                    cluster_throughput[cluster_id] = {}
                    
                cluster_voltage[cluster_id][round_num] = avg_voltage
                cluster_throughput[cluster_id][round_num] = total_throughput

def count_bytes_without_trailing_zeros(value):
    # Menghitung jumlah byte dari nilai string tanpa angka nol di belakang koma
    return len(value.rstrip('0').rstrip('.') if '.' in value else value)

def read_serial():
    global round_count, capture_data, current_data, node_data
    try:
        while True:
            line = ser.readline()
            try:
                line = line.decode('utf-8').strip()
            except UnicodeDecodeError:
                print("Terjadi kesalahan dekode, melewatkan baris")
                continue  # Melewatkan baris yang tidak dapat didekode
            print(line)
            if line.startswith("Starting round"):
                round_count += 1
                if round_count > 1 and current_data:
                    save_data_to_file(current_data)
                    current_data = []
                capture_data = False
            elif line.startswith("Rekap Data:"):
                capture_data = True
            elif line.startswith("Ronde, ID, PosisiX, PosisiY, Energi Awal, Suhu, Kelembaban, Gas, Tegangan, Cluster, CH, CH ID"):
                continue  # Skip header line
            elif capture_data:
                parts = line.split(', ')
                if len(parts) == 12:
                    node_id = int(parts[1])
                    cluster_id = int(parts[9])
                    voltage = float(parts[8])
                    
                    temperature_bytes = count_bytes_without_trailing_zeros(parts[5])
                    humidity_bytes = count_bytes_without_trailing_zeros(parts[6])
                    gas_bytes = count_bytes_without_trailing_zeros(parts[7])
                    voltage_bytes = count_bytes_without_trailing_zeros(parts[8])
                    
                    received_bytes = temperature_bytes + humidity_bytes + gas_bytes + voltage_bytes  # Hitung total bytes dari suhu, kelembaban, gas, dan tegangan
                    
                    if cluster_id not in node_colors:
                        node_colors[cluster_id] = colors[len(node_colors) % len(colors)]

                    if round_count in node_data:
                        if cluster_id in node_data[round_count]:
                            if node_id in node_data[round_count][cluster_id]:
                                node_data[round_count][cluster_id][node_id].append({'voltage': voltage, 'throughput': received_bytes})
                            else:
                                node_data[round_count][cluster_id][node_id] = [{'voltage': voltage, 'throughput': received_bytes}]
                        else:
                            node_data[round_count][cluster_id] = {node_id: [{'voltage': voltage, 'throughput': received_bytes}]}
                    else:
                        node_data[round_count] = {cluster_id: {node_id: [{'voltage': voltage, 'throughput': received_bytes}]}}

                    parts.append(received_bytes)
                    current_data.append([round_count] + parts)
                calculate_averages()
                    
    except KeyboardInterrupt:
        print("Program dihentikan.")
        if current_data:
            save_data_to_file(current_data)
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")
        if current_data:
            save_data_to_file(current_data)
    finally:
        ser.close()
        print("Serial port ditutup.")

# Menjalankan thread untuk pembacaan serial
serial_thread = threading.Thread(target=read_serial)
serial_thread.start()

# Grafik animasi
ani = FuncAnimation(fig, update_graph, interval=1000)
plt.show()

# Menunggu thread serial selesai
serial_thread.join()
