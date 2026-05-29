import pygame
import socket
import pickle
import struct
import logging



# ==================== Constants ====================
SERVER_IP = "127.0.0.1"
PORT = 5555
SCREEN_WIDTH, SCREEN_HEIGHT = 1000, 1000

PLATFORMS = [
    pygame.Rect(0,   900, 1000, 10),
    pygame.Rect(100, 700,  900, 10),
    pygame.Rect(0,   500,  900, 10),
    pygame.Rect(100, 300,  900, 10),
    pygame.Rect(0,   100,  600, 10),
]
LADDER_POSITIONS = [(850, 700), (150, 500), (750, 300)]

ACTION_TO_KEY = {
    "LEFT":  pygame.K_LEFT,
    "RIGHT": pygame.K_RIGHT,
    "UP":    pygame.K_UP,
    "DOWN":  pygame.K_DOWN,
    "SPACE": pygame.K_SPACE,
}

# ==================== Network Helpers ====================
def send_message(connection, data):
    """Sends data over the socket with a 4-byte size prefix so the packet never breaks"""
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

# ==================== Connect to Server ====================
def connect_to_server():
    """Creates a TCP connection to the server and receives our player number"""
    connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        connection.connect((SERVER_IP, PORT))
        logging.info(f"Socket connected to {SERVER_IP}:{PORT}, waiting for player number...")
        server_info = receive_message(connection)
        if server_info is None:
            logging.error("Got None from server — connection failed!")
            exit()
        player_number = server_info["player_num"]
        logging.info(f"Connected! You are Player {player_number}")
        return connection, player_number
    except Exception as error:
        logging.error(f"Could not connect to server: {error}")
        exit()

# ==================== Load Graphics ====================
def load_image(file_name, size):
    """Loads an image from disk — if missing, returns a grey rectangle instead"""
    try:
        image = pygame.image.load(file_name).convert_alpha()
        logging.debug(f"Loaded image: {file_name}")
        return pygame.transform.scale(image, size)
    except:
        logging.warning(f"Image not found: {file_name} — using placeholder")
        placeholder = pygame.Surface(size, pygame.SRCALPHA)
        placeholder.fill((200, 200, 200))
        return placeholder

def load_assets():
    """Loads all images and fonts the game needs"""
    logging.info("Loading assets...")
    player_image = load_image("Player1-removebg-preview (1).png", (50, 50))
    ladder_image = load_image("Ladder-removebg-preview.png", (50, 200))
    winner_font  = pygame.font.SysFont("Arial", 60, bold=True)
    logging.info("Assets loaded successfully")
    return player_image, ladder_image, winner_font

# ==================== Collect Keys ====================
def collect_pressed_keys():
    """Returns a dict of which actions are currently pressed, to send to the server"""
    all_keys_pressed = pygame.key.get_pressed()
    return {action: bool(all_keys_pressed[key_code]) for action, key_code in ACTION_TO_KEY.items()}

# ==================== Draw ====================
def draw_game(screen, assets, game_state):
    """Draws all game elements based on the state received from the server"""
    player_image, ladder_image, winner_font = assets

    screen.fill((30, 30, 30))

    for platform in PLATFORMS:
        pygame.draw.rect(screen, (139, 69, 19), platform)

    for ladder_pos in LADDER_POSITIONS:
        screen.blit(ladder_image, ladder_pos)

    screen.blit(player_image, game_state["p1"])
    screen.blit(player_image, game_state["p2"])

    for barrel_x, barrel_y in game_state["barrels"]:
        pygame.draw.circle(screen, (255, 140, 0), (int(barrel_x) + 15, int(barrel_y) + 15), 15)

    if game_state["winner"]:
        winner_text = winner_font.render(game_state["winner"], True, (255, 215, 0))
        restart_text = pygame.font.SysFont("Arial", 35).render("Press R to play again", True, (255, 255, 255))
        screen.blit(winner_text, (SCREEN_WIDTH // 2 - winner_text.get_width() // 2, SCREEN_HEIGHT // 2 - 50))
        screen.blit(restart_text, (SCREEN_WIDTH // 2 - restart_text.get_width() // 2, SCREEN_HEIGHT // 2 + 30))

    pygame.display.update()

# ==================== Game Loop ====================
def game_loop(connection, screen, assets, player_number):
    """Main loop — sends keys to server, receives game state, draws the screen"""
    clock = pygame.time.Clock()
    game_state = {"p1": (50, 850), "p2": (150, 850), "barrels": [], "winner": ""}
    logging.info("Game loop started")

    while True:
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                logging.info("Player closed the window")
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r and game_state["winner"]:
                    logging.info(f"Player {player_number} voted to restart")
                    send_message(connection, {"restart": True})

        try:
            send_message(connection, collect_pressed_keys())
            received_state = receive_message(connection)
            if received_state:
                game_state = received_state
        except Exception as error:
            logging.error(f"Connection error: {error}")
            return

        draw_game(screen, assets, game_state)

# ==================== Main ====================
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

    assets = load_assets()
    connection, player_number = connect_to_server()

    pygame.display.set_caption(f"Donkey Kong - Player {player_number}")

    game_loop(connection, screen, assets, player_number)

    connection.close()
    logging.info("Disconnected from server")
    pygame.quit()

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler("client.log"),
            logging.StreamHandler()
        ]
    )
    main()
