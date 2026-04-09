import pygame
import random

pygame.init()

# 📺 הגדרות מסך
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 1000
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Donkey Kong Style - גרסה ללא ירידה בסולמות")
clock = pygame.time.Clock()

# 🎨 צבעים
BG_COLOR = (20, 20, 20)
RED = (200, 50, 50)
BLUE = (50, 150, 255)
ORANGE = (255, 140, 0)

# 🧱 פלטפורמות (עם רווחים בקצוות כדי שהחביות ייפלו לקומה הבאה)
platforms = [
    pygame.Rect(0, 900, 1000, 10),  # רצפה תחתונה
    pygame.Rect(100, 700, 900, 10),  # חור בצד שמאל
    pygame.Rect(0, 500, 900, 10),  # חור בצד ימין
    pygame.Rect(100, 300, 900, 10),  # חור בצד שמאל
    pygame.Rect(0, 100, 600, 10),  # פלטפורמה עליונה
]

# 🪜 סולמות
ladders = [
    pygame.Rect(850, 700, 50, 200),
    pygame.Rect(150, 500, 50, 200),
    pygame.Rect(750, 300, 50, 200),
    pygame.Rect(500, 100, 50, 200),
]


# 🧍 מחלקת שחקן
class Player:
    def __init__(self, x, y):
        self.size = (50, 50)
        try:
            self.image = pygame.image.load("Player1.png")
            self.image = pygame.transform.scale(self.image, self.size)
        except:
            self.image = pygame.Surface(self.size)
            self.image.fill((0, 255, 0))

        self.start_x = x
        self.start_y = y
        self.x = x
        self.y = y

        self.speed = 5
        self.velocity_y = 0
        self.gravity = 0.6
        self.jump_power = -12
        self.on_ground = False

    def get_rect(self):
        return pygame.Rect(self.x, self.y, *self.size)

    def reset_position(self):
        self.x = self.start_x
        self.y = self.start_y
        self.velocity_y = 0

    def move(self, keys, platforms, ladders):
        rect = self.get_rect()
        on_ladder = any(rect.colliderect(l) for l in ladders)

        # תנועה אופקית
        if keys[pygame.K_LEFT]:
            self.x -= self.speed
        if keys[pygame.K_RIGHT]:
            self.x += self.speed

        # קפיצה
        if keys[pygame.K_SPACE] and self.on_ground:
            self.velocity_y = self.jump_power

        # לוגיקת סולמות
        if on_ladder:
            self.velocity_y = 0
            if keys[pygame.K_UP]: self.y -= 5
            if keys[pygame.K_DOWN]: self.y += 5
        else:
            self.velocity_y += self.gravity

        self.y += self.velocity_y

        # בדיקת התנגשות עם פלטפורמות
        rect = self.get_rect()
        self.on_ground = False
        for p in platforms:
            if rect.colliderect(p):
                if self.velocity_y > 0:  # נופל מלמעלה
                    self.y = p.top - self.size[1]
                    self.velocity_y = 0
                    self.on_ground = True
                elif self.velocity_y < 0:  # קופץ מלמטה
                    self.y = p.bottom
                    self.velocity_y = 0

        # גבולות מסך
        self.x = max(0, min(self.x, SCREEN_WIDTH - self.size[0]))

    def draw(self, screen):
        screen.blit(self.image, (self.x, self.y))


# 🛢️ מחלקת חבית (ללא ירידה בסולמות)
class Barrel:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 30, 30)
        self.speed_x = 4  # המהירות שבה היא מתגלגלת
        self.velocity_y = 0
        self.gravity = 0.6

    def update(self, platforms):
        # הפעלת כבידה תמידית (כדי שתיפול ברווחים)
        self.velocity_y += self.gravity
        self.rect.y += self.velocity_y

        # בדיקת התנגשות עם פלטפורמות - עוצרת את הנפילה
        for p in platforms:
            if self.rect.colliderect(p):
                if self.velocity_y > 0:
                    self.rect.bottom = p.top
                    self.velocity_y = 0

        # תנועה קדימה
        self.rect.x += self.speed_x

        # אם פגעה בקיר - משנה כיוון
        if self.rect.right >= SCREEN_WIDTH or self.rect.left <= 0:
            self.speed_x *= -1

    def draw(self, screen):
        pygame.draw.circle(screen, ORANGE, self.rect.center, 15)
        # קו שמראה שהיא מתגלגלת
        pygame.draw.line(screen, (0, 0, 0), self.rect.center, (self.rect.centerx, self.rect.top), 2)


# --- אובייקטים וטיימרים ---
player = Player(50, 850)
barrels = []

# יצירת חבית כל 2.5 שניות
SPAWN_BARREL = pygame.USEREVENT + 1
pygame.time.set_timer(SPAWN_BARREL, 2500)

# 🎮 לולאה ראשית
running = True
while running:
    clock.tick(60)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == SPAWN_BARREL:
            barrels.append(Barrel(50, 50))  # נוצרת ליד הקוף למעלה

    keys = pygame.key.get_pressed()
    player.move(keys, platforms, ladders)

    # עדכון חביות
    for barrel in barrels[:]:
        barrel.update(platforms)

        # התנגשות בשחקן
        if barrel.rect.colliderect(player.get_rect()):
            player.reset_position()
            barrels.clear()  # ניקוי חביות אחרי פסילה
            break

        # היעלמות בנקודת הסיום (למטה בצד שמאל)
        if barrel.rect.y >= 850 and barrel.rect.x < 30:
            barrels.remove(barrel)
            continue

        # הגנה מפני חביות שבורחות מהמסך
        if barrel.rect.top > SCREEN_HEIGHT:
            barrels.remove(barrel)

    # 🎨 ציור
    screen.fill(BG_COLOR)
    for p in platforms:
        pygame.draw.rect(screen, RED, p)
    for l in ladders:
        pygame.draw.rect(screen, BLUE, l)
    for barrel in barrels:
        barrel.draw(screen)
    player.draw(screen)

    pygame.display.update()

pygame.quit()
