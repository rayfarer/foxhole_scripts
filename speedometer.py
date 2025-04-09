import tkinter as tk
import math
import pygame
import threading
import time

CANVAS_SIZE = 500
CENTER_X = CANVAS_SIZE / 2
CENTER_Y = CANVAS_SIZE / 2
RADIUS = CANVAS_SIZE * 0.4
ARC_WIDTH = 15
# You can set your own max speed / acceleration rate etc. here
MAX_SPEED = 17.4  # m/s
UPDATE_MS = 16
SPEED_STEP = 0.1

# Gauge Arc Geometry
ARC_START_ANGLE = 225
ARC_EXTENT = 270

# You can set your own colors here
# --- Deep Orange Color Palette ---
DEEP_ORANGE_MAIN = '#FF6600'
DEEP_ORANGE_BRIGHT = '#FF8C00'
# DEEP_ORANGE_DIM = '#CC5500' # No longer needed
DEEP_ORANGE_DARK = '#803300'
BACKGROUND_COLOR = '#1A0A00'

# Assigning colors to elements
BG_COLOR = BACKGROUND_COLOR
ARC_BG_COLOR = DEEP_ORANGE_DARK
ARC_MAIN_COLOR_START = DEEP_ORANGE_MAIN # Color for the filling arc
ARC_MAIN_COLOR_END = DEEP_ORANGE_MAIN
TICK_COLOR = DEEP_ORANGE_MAIN
NUMBER_COLOR = DEEP_ORANGE_MAIN
# NEEDLE_COLOR = DEEP_ORANGE_BRIGHT # Not used
# CENTER_BG_COLOR = DEEP_ORANGE_DARK # Not used
DIGITAL_SPEED_COLOR = DEEP_ORANGE_BRIGHT
# CLOCK_COLOR = DEEP_ORANGE_DIM # Not used

# Fonts
MAIN_FONT = "Segoe UI"
# MAIN_FONT = "Arial"
DIGITAL_FONT_SIZE = 50
NUMBER_FONT_SIZE = 12
# CLOCK_FONT_SIZE = 14 # Not used

class ModernSpeedometerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Modern Speedometer (m/s)")
        self.root.geometry(f'{CANVAS_SIZE + 20}x{CANVAS_SIZE + 100}')
        self.root.config(bg=BG_COLOR)

        self.current_speed = 0.0
        self.target_speed = 0.0
        self.trigger_value = 0.0

        # --- Center Digital Display Area ---
        self.digital_label = tk.Label(root, text="0.0 m/s",
                                      font=(MAIN_FONT, DIGITAL_FONT_SIZE, "bold"),
                                      fg=DIGITAL_SPEED_COLOR, bg=BG_COLOR)
        self.digital_label.place(relx=0.5, rely=0.5, anchor='center')

        # --- Canvas ---
        self.canvas = tk.Canvas(root, width=CANVAS_SIZE, height=CANVAS_SIZE,
                                bg=BG_COLOR, highlightthickness=0)
        self.canvas.pack(pady=(20, 0))

        self.digital_label.lift()

        # --- Draw static elements (background arc, line ticks, numbers) ---
        self.draw_static_elements()

        # --- Create the Dynamic Fill Arc ---
        self.fill_arc = self.canvas.create_arc(
            CENTER_X - RADIUS, CENTER_Y - RADIUS,
            CENTER_X + RADIUS, CENTER_Y + RADIUS,
            start=ARC_START_ANGLE,
            extent=0,
            outline=DEEP_ORANGE_MAIN,
            width=ARC_WIDTH,
            style=tk.ARC
        )

        # --- Pygame Controller Initialization ---
        try:
            pygame.init()
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
                print(f"Initialized Joystick: {self.joystick.get_name()}")
            else:
                print("Error: No joystick detected.")
                self.joystick = None
        except pygame.error as e:
            print(f"Pygame error: {e}")
            self.joystick = None

        # --- Controller Polling Thread ---
        self.running = True
        if self.joystick:
            self.poll_thread = threading.Thread(target=self.poll_controller, daemon=True)
            self.poll_thread.start()

        # --- Start Update Loop ---
        self.update_speed()

    def get_angle_deg_from_speed(self, speed):
        """ Maps speed (0-MAX_SPEED) to Tkinter angle (degrees) along the arc. """
        if MAX_SPEED <= 0: return ARC_START_ANGLE
        speed_ratio = max(0, min(speed / MAX_SPEED, 1.0))
        angle_deg = ARC_START_ANGLE - (speed_ratio * ARC_EXTENT)
        return angle_deg

    def draw_static_elements(self):
        """ Draws the fixed background parts of the speedometer face. """

        # 1. Background Arc (Full track)
        self.canvas.create_arc(CENTER_X - RADIUS, CENTER_Y - RADIUS,
                               CENTER_X + RADIUS, CENTER_Y + RADIUS,
                               start=ARC_START_ANGLE, extent=ARC_EXTENT,
                               outline=ARC_BG_COLOR, width=ARC_WIDTH, style=tk.ARC)

        # 2. Main Colored Arc segments are REMOVED (replaced by dynamic fill_arc)

        # 3. Tick Marks (Lines) and Numbers
        tick_length = 30 # Length of the tick lines
        major_tick_interval = 2
        num_major_ticks = int(MAX_SPEED // major_tick_interval)

        for i in range(num_major_ticks + 1):
            speed_value = i * major_tick_interval
            tick_angle_deg = self.get_angle_deg_from_speed(speed_value)
            tick_angle_rad = math.radians(tick_angle_deg)

            # --- Calculate points for LINE tick mark ---
            # Start point (on the arc)
            x_start = CENTER_X + RADIUS * math.cos(tick_angle_rad)
            y_start = CENTER_Y - RADIUS * math.sin(tick_angle_rad)
            # End point (inwards from the arc)
            x_end = CENTER_X + (RADIUS - tick_length) * math.cos(tick_angle_rad)
            y_end = CENTER_Y - (RADIUS - tick_length) * math.sin(tick_angle_rad)

            # --- Draw the line tick mark ---
            self.canvas.create_line(x_start, y_start, x_end, y_end,
                                    fill=TICK_COLOR, width=2) # Use create_line, set width

            # Numbers outside the arc (remains the same)
            num_radius = RADIUS + 25
            num_x = CENTER_X + num_radius * math.cos(tick_angle_rad)
            num_y = CENTER_Y - num_radius * math.sin(tick_angle_rad)
            self.canvas.create_text(num_x, num_y, text=str(int(speed_value)),
                                     fill=NUMBER_COLOR, font=(MAIN_FONT, NUMBER_FONT_SIZE))

        # Optional: Add a small final LINE tick mark exactly at MAX_SPEED
        final_tick_angle_deg = self.get_angle_deg_from_speed(MAX_SPEED)
        final_tick_angle_rad = math.radians(final_tick_angle_deg)
        final_tick_length = tick_length * 0.7 # Make it slightly shorter if desired

        ft_x_start = CENTER_X + RADIUS * math.cos(final_tick_angle_rad)
        ft_y_start = CENTER_Y - RADIUS * math.sin(final_tick_angle_rad)
        ft_x_end = CENTER_X + (RADIUS - final_tick_length) * math.cos(final_tick_angle_rad)
        ft_y_end = CENTER_Y - (RADIUS - final_tick_length) * math.sin(final_tick_angle_rad)
        # Draw the final line tick
        self.canvas.create_line(ft_x_start, ft_y_start, ft_x_end, ft_y_end,
                                fill=TICK_COLOR, width=2)

        # 4. Central Display Background - REMOVED previously

    def poll_controller(self):
        """ Polls the joystick in a separate thread. """
        while self.running:
            if self.joystick:
                try:
                    pygame.event.pump()
                    raw_value = self.joystick.get_axis(5) # Verify Axis!
                    self.trigger_value = max(0.0, min((raw_value + 1.0) / 2.0, 1.0))
                except pygame.error as e:
                    print(f"Joystick error: {e}")
                    self.trigger_value = 0.0
                    time.sleep(1)
            else:
                self.trigger_value = 0.0
            time.sleep(0.01)

    def update_speed(self):
        """ Main update loop called by Tkinter's 'after'. """
        if not self.running:
            return

        self.target_speed = self.trigger_value * MAX_SPEED

        # Speed smoothing logic
        speed_diff = self.target_speed - self.current_speed
        change = max(-SPEED_STEP, min(SPEED_STEP, speed_diff))
        if abs(speed_diff) < SPEED_STEP / 2 and self.trigger_value < 0.05:
             self.current_speed *= 0.95
        else:
             self.current_speed += change
        self.current_speed = max(0.0, min(self.current_speed, MAX_SPEED))

        # Update Digital Display
        self.digital_label.config(text=f"{self.current_speed:.1f} m/s")

        # --- Update the Fill Arc ---
        speed_ratio = max(0, min(self.current_speed / MAX_SPEED, 1.0)) if MAX_SPEED > 0 else 0
        new_extent = -speed_ratio * ARC_EXTENT
        self.canvas.itemconfigure(self.fill_arc, extent=new_extent)

        # Lift digital label
        self.digital_label.lift()

        # Schedule the next update
        self.root.after(UPDATE_MS, self.update_speed)

    def stop(self):
        """ Stops the application gracefully. """
        print("Stopping application...")
        self.running = False
        if self.joystick:
             pygame.quit()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ModernSpeedometerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.stop)
    root.mainloop()