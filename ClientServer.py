import socket

# Skriv IP-adressen på din Raspberry Pi
HOST = "192.168.0.100"  # <- Skift til Pi'ens IP
PORT = 5000

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))

print("Forbundet til Raspberry Pi!")

while True:
    cm = input("Indtast vinduesåbning i cm (0.5 - 15): ")

    # Afslut hvis man skriver quit
    if cm.lower() == "quit":
        print("Lukker forbindelse...")
        client.close()
        break
    
    client.send(cm.encode())
    response = client.recv(1024).decode()
    print("Svar fra Pi:", response)
