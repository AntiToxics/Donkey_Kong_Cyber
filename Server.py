import socket
import pickle
import random
import threading
import struct
import time
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler("server.log"),
        logging.StreamHandler()
    ]
)

# ==================== Constants ====================
PORT = 5555
FRAME_RATE = 1 / 60

PLATFORMS = [
    (0,   900, 1000, 10),
    (100, 700,  900, 10),
    (0,   500,  900, 10),
    (100, 300,  900, 10),
    (0,   100,  600, 10),
]
LADDERS = [
    (850, 700, 50, 200),
    (150, 500, 50, 200),
    (750, 300, 50, 200),
]

ACTION_KEYS = {"left": "LEFT", "right": "RIGHT", "up": "UP", "down": "DOWN", "jump": "SPACE"}

# ==================== Network Helpers ====================
def send_message(connection, data):
    """Sends data with a 4-byte size prefix so the packet never breaks"""
    raw_bytes = pickle.dumps(data)
    size_prefix = struct.pack(">I", len(raw_bytes))
    connection.sendall(size_prefix + raw_bytes)

def receive_message(connection):
    """Receives a full message by first reading the 4-byte size prefix"""
    size_bytes = receive_exact_bytes(connection, 4)
    if not size_bytes:
        return None
    message_length = struct.unpack(">I", size_bytes)[0]
    raw_bytes = receive_exact_bytes(connection, message_length)
    return pickle.loads(raw_bytes) if raw_bytes else None

def receive_exact_bytes(connection, num_bytes):
    """Keeps reading from the socket until we have exactly num_bytes"""
    buffer = b""
    while len(buffer) < num_bytes:
        chunk = connection.recv(num_bytes - len(buffer))
        if not chunk:
            return None
        buffer += chunk
    return buffer

# ==================== Setup Network ====================
def setup_network():
    """Opens the server and waits for both players to connect"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("0.0.0.0", PORT))
    server_socket.listen(2)
    logging.info(f"Server started on port {PORT}")

    logging.info("Waiting for Player 1...")
    player1_conn, player1_addr = server_socket.accept()
    send_message(player1_conn, {"player_num": 1})
    logging.info(f"Player 1 connected from {player1_addr}")

    logging.info("Waiting for Player 2...")
    player2_conn, player2_addr = server_socket.accept()
    send_message(player2_conn, {"player_num": 2})
    logging.info(f"Player 2 connected from {player2_addr}")

    return server_socket, player1_conn, player2_conn

# ==================== Client Thread ====================
def handle_player_input(connection, player_number, keys_store, keys_lock, restart_votes):
    """
    Runs in a background thread for each player.
    Receives key presses and stores them in keys_store.
    """
    while True:
        try:
            received_keys = receive_message(connection)
            if received_keys is None:
                break
            if received_keys.get("restart"):
                with keys_lock:
                    restart_votes.add(player_number)
                logging.debug(f"Player {player_number} voted to restart")
            else:
                with keys_lock:
                    keys_store[player_number] = received_keys
        except Exception as e:
            logging.error(f"Error receiving from Player {player_number}: {e}")
            break
    logging.warning(f"Player {player_number} disconnected")

# ==================== Game Classes ====================
class Player:
    def __init__(self, start_x, start_y, action_keys):
        self.x = float(start_x)
        self.y = float(start_y)
        self.vertical_velocity = 0.0
        self.is_jumping = False
        self.won = False
        self.action_keys = action_keys

    def is_colliding_with(self, rect_x, rect_y, rect_width, rect_height):
        return (self.x < rect_x + rect_width and self.x + 50 > rect_x and
                self.y < rect_y + rect_height and self.y + 50 > rect_y)

    def update(self, pressed_keys):
        if not pressed_keys:
            return

        keys = self.action_keys
        on_ladder = any(self.is_colliding_with(*ladder) for ladder in LADDERS)

        if pressed_keys.get(keys["left"]):
            self.x -= 5
        if pressed_keys.get(keys["right"]):
            self.x += 5

        if on_ladder and (pressed_keys.get(keys["up"]) or pressed_keys.get(keys["down"])):
            self.vertical_velocity = 0
            if pressed_keys.get(keys["up"]):
                self.y -= 5
            if pressed_keys.get(keys["down"]):
                self.y += 5
        else:
            self.vertical_velocity += 0.8
            self.y += self.vertical_velocity
            on_ground = False
            for (px, py, pw, ph) in PLATFORMS:
                if self.is_colliding_with(px, py, pw, ph) and self.vertical_velocity > 0:
                    self.y = py - 50
                    self.vertical_velocity = 0
                    on_ground = True
                    self.is_jumping = False

            if pressed_keys.get(keys["jump"]) and on_ground and not self.is_jumping:
                self.vertical_velocity = -14
                self.is_jumping = True

        self.x = max(0, min(self.x, 950))

        if self.x <= 150 and 250 <= self.y <= 350:
            self.won = True


class Barrel:
    def __init__(self):
        self.x = float(random.randint(200, 250))
        self.y = 50.0
        self.horizontal_speed = random.choice([-4.0, 4.0])

    def is_hitting_player(self, player):
        return (player.x < self.x + 30 and player.x + 50 > self.x and
                player.y < self.y + 30 and player.y + 50 > self.y)

    def update(self):
        self.y += 4
        self.x += self.horizontal_speed
        for (px, py, pw, ph) in PLATFORMS:
            if (self.x < px + pw and self.x + 30 > px and
                    self.y < py + ph and self.y + 30 > py):
                self.y = py - 30
        if self.x + 30 >= 1000 or self.x <= 0:
            self.horizontal_speed *= -1

# ==================== Game Loop ====================
def game_loop(player1_conn, player2_conn, keys_store, keys_lock, restart_votes):
    """Main loop — updates physics, checks collisions, sends game state to both clients"""
    player1 = Player(50,  850, ACTION_KEYS)
    player2 = Player(150, 850, ACTION_KEYS)
    barrels = []
    winner_message = ""

    while True:
        frame_start = time.time()

        with keys_lock:
            if len(restart_votes) == 2:
                player1 = Player(50,  850, ACTION_KEYS)
                player2 = Player(150, 850, ACTION_KEYS)
                barrels = []
                winner_message = ""
                restart_votes.clear()
                logging.info("Game restarted by both players")

        if not winner_message:
            with keys_lock:
                player1_keys = dict(keys_store.get(1, {}))
                player2_keys = dict(keys_store.get(2, {}))

            player1.update(player1_keys)
            player2.update(player2_keys)

            if random.random() < 0.01:
                barrels.append(Barrel())
                logging.debug(f"New barrel spawned — total barrels: {len(barrels)}")

            for barrel in barrels[:]:
                barrel.update()
                if barrel.is_hitting_player(player1):
                    winner_message = "Player 2 Wins! (P1 Hit)"
                    logging.info("Player 1 was hit by a barrel — Player 2 wins!")
                if barrel.is_hitting_player(player2):
                    winner_message = "Player 1 Wins! (P2 Hit)"
                    logging.info("Player 2 was hit by a barrel — Player 1 wins!")
                if barrel.y > 1000:
                    barrels.remove(barrel)

            if player1.won:
                winner_message = "Player 1 Wins!"
                logging.info("Player 1 reached the goal and won!")
            if player2.won:
                winner_message = "Player 2 Wins!"
                logging.info("Player 2 reached the goal and won!")

        game_state = {
            "p1":      (player1.x, player1.y),
            "p2":      (player2.x, player2.y),
            "barrels": [(barrel.x, barrel.y) for barrel in barrels],
            "winner":  winner_message,
        }

        try:
            send_message(player1_conn, game_state)
            send_message(player2_conn, game_state)
        except Exception as e:
            logging.error(f"Failed to send game state: {e}")
            break

        elapsed_time = time.time() - frame_start
        time.sleep(max(0, FRAME_RATE - elapsed_time))

# ==================== Main ====================
def main():
    server_socket, player1_conn, player2_conn = setup_network()

    keys_store = {}
    keys_lock = threading.Lock()
    restart_votes = set()

    threading.Thread(target=handle_player_input, args=(player1_conn, 1, keys_store, keys_lock, restart_votes), daemon=True).start()
    threading.Thread(target=handle_player_input, args=(player2_conn, 2, keys_store, keys_lock, restart_votes), daemon=True).start()

    logging.info("Both players connected! Starting game...")

    game_loop(player1_conn, player2_conn, keys_store, keys_lock, restart_votes)

    server_socket.close()
    logging.info("Server closed.")

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler("server.log"),
            logging.StreamHandler()
        ]
    )
    
    main()
