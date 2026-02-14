import socket
import time
import os

# Constants (must match receiver)
PACKET_SIZE = 1024                                  # total packet size (including the header)
SEQUENCE_ID_SIZE = 4                                # first 4 bytes of packet are the sequence id
MESSAGE_SIZE = PACKET_SIZE - SEQUENCE_ID_SIZE       # 1020 bytes of actual data per packet
RECEIVER_ADDR = ("localhost", 5001)                 # receiver address and port
TIMEOUT = 1                                         # timeout in seconds before retransmitting

# Function to read the file
# Return values: data of the file + length
def read_file():
    with open("file.mp3", "rb") as f:
        data = f.read()
    file_size = len(data)
    return data, file_size

# Function to chunk the file into packets
# Return values: packets + the final sequence id
def create_packets(data, file_size):
    packets, sequence_id = [], 0
    for i in range(0, file_size, MESSAGE_SIZE):
        chunk = data[i:i + MESSAGE_SIZE]
        packets.append((sequence_id, chunk))
        sequence_id += len(chunk)
    return packets, sequence_id

# Function to build a packet with a 4-byte header and a payload
# Return values: header + payload
def build_packet(sequence_id, payload=b''):
    header = int.to_bytes(sequence_id, SEQUENCE_ID_SIZE, signed=True, byteorder='big')
    return header + payload

# Function to send a single packet and wait for its ACK.
# Will retransmit on timeout
# Return value: the delay from the first send to ack
def send_and_wait(udp_socket, packet, sequence_id):
    first_send_time = time.time()
    acked = False

    while not acked:
        udp_socket.sendto(packet, RECEIVER_ADDR)
        try:
            ack_packet, _ = udp_socket.recvfrom(PACKET_SIZE)
            ack_id = int.from_bytes(ack_packet[:SEQUENCE_ID_SIZE], signed=True, byteorder='big')
            # ack_id > sequence_id; this means that receiver got this packet
            if ack_id > sequence_id:
                acked = True
        except socket.timeout:
            # timed out, retransmit
            pass

    delay = time.time() - first_send_time
    return delay

# Function to send an empty packet and wait for receiver to send fin
# Return value: nothing
def wait_for_fin(udp_socket, final_sequence_id):
    """Send empty packet and wait for receiver to send fin."""
    empty_packet = build_packet(final_sequence_id)
    fin_received = False

    while not fin_received:
        udp_socket.sendto(empty_packet, RECEIVER_ADDR)
        try:
            while True:
                resp, _ = udp_socket.recvfrom(PACKET_SIZE)
                resp_msg = resp[SEQUENCE_ID_SIZE:].decode()
                if resp_msg == 'fin':
                    fin_received = True
                    break
        except socket.timeout:
            pass

# Function to send a FINACK so the receiver can close
# Return value: nothing
def send_finack(udp_socket, final_sequence_id):
    finack_packet = build_packet(final_sequence_id, b'==FINACK==')
    udp_socket.sendto(finack_packet, RECEIVER_ADDR)

def send_file_stop_and_wait():
    # read the mp3 file
    data, file_size = read_file()

    # chunk the file out to create a sequence of packets
    packets, final_sequence_id = create_packets(data, file_size)

    # create udp socket and set timeout for retransmissions
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        udp_socket.settimeout(TIMEOUT)

        # start throughput timer as soon as socket is created
        start_time = time.time()

        packet_delays = []
        total_packets = len(packets)

        # send each packet one at a time, wait for ack before sending next
        for _, (sequence_id, chunk) in enumerate(packets):
            packet = build_packet(sequence_id, chunk)
            delay = send_and_wait(udp_socket, packet, sequence_id)
            packet_delays.append(delay)

        # tell receiver we're done and wait for fin
        wait_for_fin(udp_socket, final_sequence_id)
        end_time = time.time() # stop the timer

        # close the connection
        send_finack(udp_socket, final_sequence_id)

    # final metric calculations
    total_time = end_time - start_time
    return file_size / total_time, sum(packet_delays) / len(packet_delays)

def main():
    print(f"\n=== Starting Run ===")
    throughput, average_delay = send_file_stop_and_wait()

    # compute metric using formula
    metric = 0.3 * (throughput / 1000) + 0.7 / average_delay
    print(f"Run Results: throughput={throughput:.7f}, delay={average_delay:.7f}, metric={metric:.7f}")

if __name__ == "__main__":
    main()