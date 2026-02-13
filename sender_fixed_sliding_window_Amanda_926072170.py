import socket
import time

def udp_sender():
    with open('./docker/file.mp3', 'rb') as f:
        data = f.read()

    file_size = len(data)
    print(f"File size: {file_size} bytes")

    window_size = 100
    packet_size = 1024
    seq_id_size = 4
    message_size = packet_size - seq_id_size

    packets = []
    seq_id = 0
    for i in range(0, file_size, message_size):
        message = data[i:i+message_size]

        packet = int.to_bytes(i, seq_id_size, signed=True, byteorder='big') + message
        packets.append(packet)

        seq_id += message_size

    base = 0 # index of oldest unacknowledged packet
    next_packet = 0 # index of next packet to send
    receiver_address = ("127.0.0.1", 5001)

    send_times = {}  # seq_id: first send time
    ack_times = {}   # seq_id: time ACK received

    start_time = time.time()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        udp_socket.settimeout(0.5)
        
        print("starting file transfer...")

        while base < len(packets):
            while next_packet < base + window_size and next_packet < len(packets):
                packet = packets[next_packet]
                seq_id_val = next_packet * message_size

                if seq_id_val not in send_times:
                    send_times[seq_id_val] = time.time()

                udp_socket.sendto(packet, receiver_address)
                # print(f"sent packet {next_packet} with sequence id {seq_id_val}")
                next_packet += 1

            try:
                ack_packet, _ = udp_socket.recvfrom(packet_size)
                ack_seq_id = int.from_bytes(ack_packet[:seq_id_size], signed=True, byteorder='big')
                # print(f"received acknowledgement for packet {ack_seq_id}")

                # slide base forward to the next unacknowledged packet
                while base < len(packets) and (base * message_size) < ack_seq_id:
                    seq_id_base = base * message_size

                    if seq_id_base not in ack_times:
                        ack_times[seq_id_base] = time.time()
                    base += 1
                  
            except socket.timeout:
                print("timeout, resending packets")
                next_packet = base # go back n retransmission

        fin_seq_id = -1 # special sequence id for fin packet
        fin_packet = int.to_bytes(fin_seq_id, seq_id_size, signed=True, byteorder='big') + b'==FINACK'
        udp_socket.sendto(fin_packet, receiver_address)
        
        end_time = time.time()

        print("sent fin packet")
        print("file transfer complete")

        time_taken = end_time - start_time

        # compute throughput
        throughput = file_size / time_taken

        # compute average per-packet delay
        delays = [ack_times[seq] - send_times[seq] for seq in send_times if seq in ack_times]
        avg_delay = sum(delays) / len(delays) if delays else 0.0

        # compute performance metric
        performance_metric = 0.3 * throughput / 1000 + 0.7 / avg_delay if avg_delay > 0 else 0.0

        return throughput, avg_delay, performance_metric

n = 10
throughputs = []
avg_delays = []
performance_metrics = []
for i in range(n):
    print(f"---------- Trial {i+1}: ----------")
    throughput, avg_delay, performance_metric = udp_sender()
    throughputs.append(throughput)
    avg_delays.append(avg_delay)
    performance_metrics.append(performance_metric)
    print(f"throughput: {throughput} bytes/s")
    print(f"avg delay: {avg_delay} seconds")
    print(f"performance metric: {performance_metric}")
    print("----------------------------------")

avg_throughput = round(sum(throughputs) / n, 7)
avg_delay = round(sum(avg_delays) / n, 7)
avg_performance_metric = round(sum(performance_metrics) / n, 7)

print(f"{avg_throughput},\n{avg_delay},\n{avg_performance_metric}")