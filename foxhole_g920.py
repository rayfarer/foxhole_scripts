import pygame
from pynput.keyboard import Controller as KeyboardController, Key
from pynput.mouse import Controller as MouseController, Button
import time
import sys
import tkinter as tk
import math
import threading
import os
from PIL import Image, ImageTk
import pyautogui

# --- GLOBAL CONFIGURATION (for both mapper and speedometer) ---
JOYSTICK_INDEX = 0
CANVAS_SIZE = 500
CENTER_X = CANVAS_SIZE / 2
CENTER_Y = CANVAS_SIZE / 2
RADIUS = CANVAS_SIZE * 0.4
ARC_WIDTH = 15
MAX_SPEED = 17.4  # m/s (Maximum speed for the speedometer)
UPDATE_MS = 16    # Speedometer update frequency in ms
SPEED_STEP = 0.1  # For speedometer smoothing

# Gauge Arc Geometry
ARC_START_ANGLE = 225
ARC_EXTENT = 270

# Colors (Shared for a unified look)
DEEP_ORANGE_MAIN = '#FF6600'
DEEP_ORANGE_BRIGHT = '#FF8C00'
DEEP_ORANGE_DARK = '#803300'
BACKGROUND_COLOR = '#00FF00'

BG_COLOR = BACKGROUND_COLOR
ARC_BG_COLOR = DEEP_ORANGE_DARK
TICK_COLOR = DEEP_ORANGE_MAIN
NUMBER_COLOR = DEEP_ORANGE_MAIN
DIGITAL_SPEED_COLOR = DEEP_ORANGE_BRIGHT

# Fonts
MAIN_FONT = "Segoe UI"
DIGITAL_FONT_SIZE = 50
NUMBER_FONT_SIZE = 12

# --- G920 Specific Configuration (for input mapper) ---
# IMPORTANT: Confirm these values using the separate 'wheel_tester.py' script
# (the one that prints axis and button numbers as you move the wheel/pedals).

# Shifter Button Mapping
SHIFTER_BUTTON_F = 14
BUTTON_LEFT = 5  # Button 5 for left arrow
BUTTON_RIGHT = 4  # Button 4 for right arrow
BUTTON_E = 2  # Changed to Button 2
BUTTON_TOGGLE_ACCEL_KEY = 15
BUTTON_M = 7
BUTTON_LMB = 9  # Changed to Button 9
BUTTON_RMB = 8  # Changed to Button 8
BUTTON_CTRL_Q = 3  # Changed to Button 3
BUTTON_TOGGLE_DPAD = 6  # New: Toggle between WASD and Mouse movement for D-pad
BUTTON_T = 1  # Changed to Button 1
BUTTON_END = 10  # Button 10 for End key
BUTTON_SPRINT = 0  # Button 0 for sprint toggle (left shift)
BUTTON_L = 11  # New: Button 11 for 'L' key

# Wheel Axis Mapping
STEERING_AXIS = 0
ACCELERATOR_AXIS = 1 # Accelerator pedal (typically inverted)
BRAKE_AXIS = 2       # Brake pedal - Will be mapped to 'E' key and Spacebar
CLUTCH_AXIS = 3      # Clutch pedal - Will be mapped to 'E' key

# D-pad (Hat) Mapping
DPAD_HAT_INDEX = 0 # Typically 0 for the first D-pad/hat
DPAD_MOUSE_SENSITIVITY = 10 # Pixels to move mouse per D-pad press per update cycle. Adjust as needed.

# Thresholds for Input Activation (ADJUST THESE TO FINE-TUNE FEEL)
STEERING_DEADZONE = 0.05
STEERING_THRESHOLD = 0.2
ACCELERATOR_THRESHOLD = 0.8  # For INVERTED LOGIC: value is HIGH (e.g., 0.99) when released, LOW (e.g., -0.99) when pressed.
                             # Threshold should be HIGHER than pressed, LOWER than released.
BRAKE_THRESHOLD = 0.8        # For INVERTED LOGIC: value is HIGH (e.g., 0.99) when released, LOW (e.g., -0.99) when pressed.
                             # Adjust this value based on your desired activation point.

class ModernSpeedometer:
    def __init__(self, root, canvas, digital_label):
        self.root = root
        self.canvas = canvas
        self.digital_label = digital_label
        self.current_speed = 0.0
        self.target_speed = 0.0 # This will be set by the G920MasterApp
        self.running = True

        self.first_person_mode = True  # Toggle this dynamically later if needed
        self.last_camera_direction = None  # None / 'left' / 'right'
        self.camera_tap_cooldown = 0.2  # Seconds between taps
        self.last_camera_tap_time = time.time()

        self.draw_static_elements()

        self.fill_arc = self.canvas.create_arc(
            CENTER_X - RADIUS, CENTER_Y - RADIUS,
            CENTER_X + RADIUS, CENTER_Y + RADIUS,
            start=ARC_START_ANGLE,
            extent=0,
            outline=DEEP_ORANGE_MAIN,
            width=ARC_WIDTH,
            style=tk.ARC
        )

        self.digital_label.lift() # Ensure label is on top

    def get_angle_deg_from_speed(self, speed):
        if MAX_SPEED <= 0: return ARC_START_ANGLE
        speed_ratio = max(0, min(speed / MAX_SPEED, 1.0))
        angle_deg = ARC_START_ANGLE - (speed_ratio * ARC_EXTENT)
        return angle_deg

    def draw_static_elements(self):
        self.canvas.create_arc(CENTER_X - RADIUS, CENTER_Y - RADIUS,
                               CENTER_X + RADIUS, CENTER_Y + RADIUS,
                               start=ARC_START_ANGLE, extent=ARC_EXTENT,
                               outline=ARC_BG_COLOR, width=ARC_WIDTH, style=tk.ARC)

        tick_length = 30
        major_tick_interval = 2
        num_major_ticks = int(MAX_SPEED // major_tick_interval)

        for i in range(num_major_ticks + 1):
            speed_value = i * major_tick_interval
            tick_angle_deg = self.get_angle_deg_from_speed(speed_value)
            tick_angle_rad = math.radians(tick_angle_deg)

            x_start = CENTER_X + RADIUS * math.cos(tick_angle_rad)
            y_start = CENTER_Y - RADIUS * math.sin(tick_angle_rad)
            x_end = CENTER_X + (RADIUS - tick_length) * math.cos(tick_angle_rad)
            y_end = CENTER_Y - (RADIUS - tick_length) * math.sin(tick_angle_rad)
            self.canvas.create_line(x_start, y_start, x_end, y_end,
                                     fill=TICK_COLOR, width=2)

            num_radius = RADIUS + 25
            num_x = CENTER_X + num_radius * math.cos(tick_angle_rad)
            num_y = CENTER_Y - num_radius * math.sin(tick_angle_rad)
            self.canvas.create_text(num_x, num_y, text=str(int(speed_value)),
                                     fill=NUMBER_COLOR, font=(MAIN_FONT, NUMBER_FONT_SIZE))

        final_tick_angle_deg = self.get_angle_deg_from_speed(MAX_SPEED)
        final_tick_angle_rad = math.radians(final_tick_angle_deg)
        final_tick_length = tick_length * 0.7

        ft_x_start = CENTER_X + RADIUS * math.cos(final_tick_angle_rad)
        ft_y_start = CENTER_Y - RADIUS * math.sin(final_tick_angle_rad)
        ft_x_end = CENTER_X + (RADIUS - final_tick_length) * math.cos(final_tick_angle_rad)
        ft_y_end = CENTER_Y - (RADIUS - final_tick_length) * math.sin(tick_angle_rad)
        self.canvas.create_line(ft_x_start, ft_y_start, ft_x_end, ft_y_end,
                                 fill=TICK_COLOR, width=2)

    def update_speed(self):
        if not self.running:
            return

        speed_diff = self.target_speed - self.current_speed
        change = max(-SPEED_STEP, min(SPEED_STEP, speed_diff))

        # Smoothed deceleration logic for speed
        if abs(speed_diff) < SPEED_STEP / 2 and self.target_speed < 0.05: # Use target_speed to check if pedal is released
            self.current_speed *= 0.95
        else:
            self.current_speed += change
        self.current_speed = max(0.0, min(self.current_speed, MAX_SPEED))

        self.digital_label.config(text=f"{self.current_speed:.1f} m/s")

        speed_ratio = max(0, min(self.current_speed / MAX_SPEED, 1.0)) if MAX_SPEED > 0 else 0
        new_extent = -speed_ratio * ARC_EXTENT
        self.canvas.itemconfigure(self.fill_arc, extent=new_extent)

        self.digital_label.lift()
        self.root.after(UPDATE_MS, self.update_speed)

class GearIndicator:
    def __init__(self, root):
        self.root = root
        self.root.title("Gear Indicator")
        self.root.geometry('100x100')
        self.root.config(bg=BG_COLOR)
        self.root.attributes('-topmost', True)
        
        self.gear_label = tk.Label(
            root,
            text="D",
            font=(MAIN_FONT, 48, "bold"),
            fg=DEEP_ORANGE_BRIGHT,
            bg=BG_COLOR
        )
        self.gear_label.pack(expand=True)

        # --- Brake indicator in a separate window ---
        self.brake_window = tk.Toplevel(root)
        self.brake_window.title("Brake Indicator")
        self.brake_window.geometry('100x100')
        self.brake_window.config(bg=BG_COLOR)
        self.brake_window.attributes('-topmost', True)
        # self.brake_window.withdraw()  # No longer hide at startup

        brake_icon_path = os.path.join('assets', 'brake.webp')
        self.brake_img = None
        if os.path.exists(brake_icon_path):
            pil_img = Image.open(brake_icon_path).resize((64, 64), Image.LANCZOS)
            self.brake_img = ImageTk.PhotoImage(pil_img)
        self.brake_label = tk.Label(self.brake_window, image=self.brake_img, bg=BG_COLOR)
        self.brake_label.pack(expand=True)
        self.brake_label.pack_forget()  # Hide icon initially

    def update_gear(self, is_forward):
        self.gear_label.config(
            text="D" if is_forward else "R",
            fg=DEEP_ORANGE_BRIGHT if is_forward else DEEP_ORANGE_MAIN
        )

    def set_brake_indicator(self, on):
        if self.brake_img is None:
            return
        if on:
            self.brake_label.pack(expand=True)
        else:
            self.brake_label.pack_forget()

class G920MasterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("G920 Input Mapper with Speedometer")
        self.root.geometry(f'{CANVAS_SIZE + 20}x{CANVAS_SIZE + 100}')
        self.root.config(bg=BG_COLOR)

        # Create gear indicator window
        self.gear_window = tk.Toplevel(root)
        self.gear_indicator = GearIndicator(self.gear_window)
        
        # Position the gear window to the right of the speedometer
        self.gear_window.geometry(f'+{CANVAS_SIZE + 40}+20')

        # First-person camera control variables
        self.first_person_mode = True  # Enable first-person camera control
        self.last_camera_direction = None
        self.last_camera_tap_time = 0
        self.camera_tap_cooldown = 0.05  # 50ms cooldown between camera direction changes
        self.camera_hold_time = 0.05  # How long to hold the camera key (50ms)

        # Transmission state
        self.is_forward = True  # True for Drive, False for Reverse
        self._last_button_15 = False  # Track button 15 state for toggle
        self._last_button_6 = False  # Track button 6 state for toggle
        self._last_button_11 = False  # Track button 11 state for 'L' key

        # Initialize Pygame and Joystick
        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() == 0:
            print("Error: No joystick found. Please ensure your G920 is plugged in and recognized.")
            self.joystick = None
        else:
            try:
                self.joystick = pygame.joystick.Joystick(JOYSTICK_INDEX)
                self.joystick.init()
                print(f"Connected to: {self.joystick.get_name()}")
                print(f"Number of Axes: {self.joystick.get_numaxes()}, Number of Buttons: {self.joystick.get_numbuttons()}, Number of Hats: {self.joystick.get_numhats()}")
            except pygame.error as e:
                print(f"Error initializing joystick at index {JOYSTICK_INDEX}: {e}")
                print("Please check your JOYSTICK_INDEX or if the wheel is connected correctly.")
                self.joystick = None

        self.keyboard = KeyboardController()
        self.mouse = MouseController()

        self.simulated_states = {
            'f': False, 'a': False, 'd': False, 'w': False, 's': False,
            Key.space: False, # Brake now uses Key.space
            ',': False, 'e': False, 'm': False, 't': False,
            'l': False,  # Add 'l' to simulated states
            'lmb': False, # Left Mouse Button state
            'rmb': False, # Right Mouse Button state
            'ctrl_q': False,
            Key.left: False,  # Track left arrow state
            Key.right: False,  # Track right arrow state
            Key.end: False,  # Track End key state
            Key.shift: False  # Track shift state
        }
        self.current_accelerator_key = 'w'
        self.dpad_as_wasd = False  # New: Track D-pad mode
        self._sprint_toggle_pressed = False  # Track sprint button state

        # --- Speedometer UI Setup ---
        self.digital_label = tk.Label(root, text="0.0 m/s",
                                      font=(MAIN_FONT, DIGITAL_FONT_SIZE, "bold"),
                                      fg=DIGITAL_SPEED_COLOR, bg=BG_COLOR)
        self.digital_label.place(relx=0.5, rely=0.45, anchor='center')

        self.canvas = tk.Canvas(root, width=CANVAS_SIZE, height=CANVAS_SIZE,
                                 bg=BG_COLOR, highlightthickness=0)
        self.canvas.pack(pady=(20, 0))

        self.speedometer = ModernSpeedometer(root, self.canvas, self.digital_label)

        # --- Handbrake sound ---
        pygame.mixer.init()
        self.handbrake_sound = None
        try:
            self.handbrake_sound = pygame.mixer.Sound(os.path.join('assets', 'handbrake.mp3'))
        except Exception as e:
            print(f"Could not load handbrake.mp3: {e}")
        self._last_button_13 = False

        # --- Start Input Polling and Speedometer Update ---
        self.running = True
        self.input_poll_thread = threading.Thread(target=self.poll_inputs, daemon=True)
        self.input_poll_thread.start()
        self.speedometer.update_speed() # Start the speedometer's own update loop

        self.print_startup_info()

    def print_startup_info(self):
        print(f"\n--- G920 Input Mapper with Speedometer Active ---")
        print(f"  Mapping: Shifter Button {SHIFTER_BUTTON_F}   -> 'F'")
        print(f"  Mapping: Steering Left (Axis {STEERING_AXIS}) -> 'A'")
        print(f"  Mapping: Steering Right (Axis {STEERING_AXIS}) -> 'D'")
        print(f"  Mapping: Accelerator (Axis {ACCELERATOR_AXIS}) -> INVERTED '{self.current_accelerator_key}' (toggle with Button {BUTTON_TOGGLE_ACCEL_KEY})")
        print(f"  Mapping: Brake Pedal (Axis {BRAKE_AXIS})       -> 'E' key and Spacebar")
        print(f"  Mapping: Clutch Pedal (Axis {CLUTCH_AXIS})     -> 'E' key")
        print(f"  Mapping: Button {BUTTON_LEFT}    -> Left Arrow")
        print(f"  Mapping: Button {BUTTON_RIGHT}   -> Right Arrow")
        print(f"  Mapping: Button {BUTTON_E}        -> 'e'")
        print(f"  Mapping: Button {BUTTON_M}        -> 'm'")
        print(f"  Mapping: Button {BUTTON_LMB}      -> Left Mouse Button")
        print(f"  Mapping: Button {BUTTON_RMB}      -> Right Mouse Button")
        print(f"  Mapping: Button {BUTTON_CTRL_Q}   -> Control + Q")
        print(f"  Mapping: Button {BUTTON_T}        -> 'T'")
        print(f"  Mapping: Button {BUTTON_END}      -> 'End'")
        print(f"  Mapping: Button {BUTTON_TOGGLE_DPAD} -> Toggle D-pad between WASD and Mouse Movement")
        print(f"  Mapping: Button {BUTTON_SPRINT}   -> Left Shift (Sprint)")
        print(f"  Mapping: Button {BUTTON_L}        -> 'L'")
        print(f"  Mapping: D-pad (Hat {DPAD_HAT_INDEX})  -> Mouse Movement (Sensitivity: {DPAD_MOUSE_SENSITIVITY})")
        print(f"  Steering Threshold: {STEERING_THRESHOLD}, Steering Deadzone: {STEERING_DEADZONE}")
        print(f"  Accelerator Threshold: {ACCELERATOR_THRESHOLD}")
        print(f"  Brake Threshold: {BRAKE_THRESHOLD}")
        print("\nPress Ctrl+C in this window or close the Tkinter window to stop the script.")
        print("------------------------------------\n")

    def press_key(self, key_to_press):
        if key_to_press == Key.space:
            if not self.simulated_states[Key.space]:
                self.keyboard.press(Key.space)
                self.simulated_states[Key.space] = True
        elif key_to_press in self.simulated_states and not self.simulated_states[key_to_press]:
            self.keyboard.press(key_to_press)
            self.simulated_states[key_to_press] = True
            # print(f"Pressed: {key_to_press}") # Uncomment for debugging key presses

    def release_key(self, key_to_release):
        if key_to_release == Key.space:
            if self.simulated_states[Key.space]:
                self.keyboard.release(Key.space)
                self.simulated_states[Key.space] = False
        elif key_to_release in self.simulated_states and self.simulated_states[key_to_release]:
            self.keyboard.release(key_to_release)
            self.simulated_states[key_to_release] = False
            # print(f"Released: {key_to_release}") # Uncomment for debugging key releases

    def poll_inputs(self):
        while self.running:
            if self.joystick:
                pygame.event.pump() # Process internal Pygame events for buttons and hats

                # --- Button Handling ---
                for i in range(self.joystick.get_numbuttons()):
                    if self.joystick.get_button(i): # Button is currently pressed
                        if i == BUTTON_TOGGLE_ACCEL_KEY:
                            if not self._last_button_15:  # Only toggle on press, not hold
                                self.is_forward = not self.is_forward
                                self.current_accelerator_key = 'w' if self.is_forward else 's'
                                self.gear_indicator.update_gear(self.is_forward)
                                print(f"Transmission toggled to {'Drive' if self.is_forward else 'Reverse'}")
                            self._last_button_15 = True
                        elif i == BUTTON_TOGGLE_DPAD:
                            if not self._last_button_6:
                                self.dpad_as_wasd = not self.dpad_as_wasd
                                print(f"D-pad mode toggled to {'WASD' if self.dpad_as_wasd else 'Arrow/Cursor'} mode")
                            self._last_button_6 = True
                        elif i == BUTTON_L:
                            if not self._last_button_11:
                                print("Button 11 pressed - 'L' key")
                                if not self.simulated_states['l']:
                                    self.keyboard.press('l')
                                    self.simulated_states['l'] = True
                            self._last_button_11 = True
                        elif i == SHIFTER_BUTTON_F:
                            self.press_key('f')
                        elif i == BUTTON_LEFT:
                            if not self.simulated_states[Key.left]:
                                print(f"Button {BUTTON_LEFT} pressed - Left Arrow")
                                self.press_key(Key.left)
                                self.simulated_states[Key.left] = True
                        elif i == BUTTON_RIGHT:
                            if not self.simulated_states[Key.right]:
                                print(f"Button {BUTTON_RIGHT} pressed - Right Arrow")
                                self.press_key(Key.right)
                                self.simulated_states[Key.right] = True
                        elif i == BUTTON_E:
                            self.press_key('e')
                        elif i == BUTTON_M:
                            self.press_key('m')
                        elif i == BUTTON_T:
                            self.press_key('t')
                        elif i == BUTTON_END:
                            if not self.simulated_states[Key.end]:
                                self.press_key(Key.end)
                                self.simulated_states[Key.end] = True
                        elif i == BUTTON_LMB:
                            if not self.simulated_states['lmb']:
                                self.mouse.press(Button.left)
                                self.simulated_states['lmb'] = True
                        elif i == BUTTON_RMB:
                            if not self.simulated_states['rmb']:
                                self.mouse.press(Button.right)
                                self.simulated_states['rmb'] = True
                        elif i == BUTTON_CTRL_Q:
                            if not self.simulated_states['ctrl_q']:
                                self.keyboard.press(Key.ctrl_l)
                                self.keyboard.press('q')
                                self.simulated_states['ctrl_q'] = True
                        elif i == BUTTON_SPRINT:
                            if not self._sprint_toggle_pressed:
                                self._sprint_toggle_pressed = True
                                print("Sprint pressed - Left Shift")
                                self.press_key(Key.shift)
                        elif i == 12:
                            if not self.simulated_states.get('e_button_12', False):
                                print("Button 12 pressed - E key")
                                self.keyboard.press('e')
                                self.simulated_states['e_button_12'] = True
                        elif i == 0:  # Button 0 centers the cursor
                            if not self.simulated_states.get('center_cursor', False):
                                screen_width, screen_height = pyautogui.size()
                                pyautogui.moveTo(screen_width // 2, screen_height // 2)
                                print("Button 0 pressed - Cursor centered")
                                self.simulated_states['center_cursor'] = True
                    else: # Button is currently released
                        if i == BUTTON_TOGGLE_ACCEL_KEY:
                            self._last_button_15 = False
                        elif i == BUTTON_TOGGLE_DPAD:
                            self._last_button_6 = False
                        elif i == BUTTON_L:
                            if self._last_button_11:
                                print("Button 11 released - 'L' key")
                                if self.simulated_states['l']:
                                    self.keyboard.release('l')
                                    self.simulated_states['l'] = False
                            self._last_button_11 = False
                        elif i == SHIFTER_BUTTON_F:
                            self.release_key('f')
                        elif i == BUTTON_LEFT:
                            if self.simulated_states[Key.left]:
                                print(f"Button {BUTTON_LEFT} released - Left Arrow")
                                self.keyboard.release(Key.left)
                                self.simulated_states[Key.left] = False
                        elif i == BUTTON_RIGHT:
                            if self.simulated_states[Key.right]:
                                print(f"Button {BUTTON_RIGHT} released - Right Arrow")
                                self.keyboard.release(Key.right)
                                self.simulated_states[Key.right] = False
                        elif i == BUTTON_E:
                            self.release_key('e')
                        elif i == BUTTON_M:
                            self.release_key('m')
                        elif i == BUTTON_T:
                            self.release_key('t')
                        elif i == BUTTON_END:
                            if self.simulated_states[Key.end]:
                                self.release_key(Key.end)
                                self.simulated_states[Key.end] = False
                        elif i == BUTTON_LMB:
                            if self.simulated_states['lmb']:
                                self.mouse.release(Button.left)
                                self.simulated_states['lmb'] = False
                        elif i == BUTTON_RMB:
                            if self.simulated_states['rmb']:
                                self.mouse.release(Button.right)
                                self.simulated_states['rmb'] = False
                        elif i == BUTTON_CTRL_Q:
                            if self.simulated_states['ctrl_q']:
                                self.keyboard.release('q')
                                self.keyboard.release(Key.ctrl_l)
                                self.simulated_states['ctrl_q'] = False
                        elif i == BUTTON_SPRINT:
                            if self._sprint_toggle_pressed:
                                self._sprint_toggle_pressed = False
                                print("Sprint released - Left Shift")
                                self.release_key(Key.shift)
                        elif i == 12:
                            if self.simulated_states.get('e_button_12', False):
                                print("Button 12 released - E key")
                                self.keyboard.release('e')
                                self.simulated_states['e_button_12'] = False
                        elif i == 0:
                            if self.simulated_states.get('center_cursor', False):
                                self.simulated_states['center_cursor'] = False

                # --- Gate open tap only when BOTH button 4 and 5 are pressed ---
                gate_open_prev = getattr(self, '_gate_open_prev', False)
                button4_down = self.joystick.get_button(4)
                button5_down = self.joystick.get_button(5)
                gate_open_now = button4_down and button5_down
                if gate_open_now and not gate_open_prev:
                    print("Buttons 4 and 5 tapped together - E key (gate open)")
                    self.keyboard.press('e')
                    self.keyboard.release('e')
                self._gate_open_prev = gate_open_now

                # --- Axis Handling (Steering, Accelerator, Brake) ---
                try:
                    # Steering
                    steering_value = self.joystick.get_axis(STEERING_AXIS)
                    if steering_value < -STEERING_THRESHOLD:
                        self.press_key('a')
                    elif self.simulated_states['a']:
                        self.release_key('a')

                    if steering_value > STEERING_THRESHOLD:
                        self.press_key('d')
                    elif self.simulated_states['d']:
                        self.release_key('d')

                    if abs(steering_value) < STEERING_DEADZONE:
                        self.release_key('a')
                        self.release_key('d')

                    # First-person camera control
                    if self.first_person_mode:
                        now = time.time()
                        steering_intensity = steering_value

                        if steering_intensity < -STEERING_THRESHOLD:
                            if self.last_camera_direction != 'left' and now - self.last_camera_tap_time > self.camera_tap_cooldown:
                                self.press_key(Key.left)
                                self.release_key(Key.right)
                                self.last_camera_direction = 'left'
                                self.last_camera_tap_time = now
                                # Schedule key release after short hold time
                                self.root.after(int(self.camera_hold_time * 1000), lambda: self.release_key(Key.left))
                        elif steering_intensity > STEERING_THRESHOLD:
                            if self.last_camera_direction != 'right' and now - self.last_camera_tap_time > self.camera_tap_cooldown:
                                self.press_key(Key.right)
                                self.release_key(Key.left)
                                self.last_camera_direction = 'right'
                                self.last_camera_tap_time = now
                                # Schedule key release after short hold time
                                self.root.after(int(self.camera_hold_time * 1000), lambda: self.release_key(Key.right))
                        else:
                            # Steering centered: release both
                            if self.last_camera_direction is not None:
                                self.release_key(Key.left)
                                self.release_key(Key.right)
                                self.last_camera_direction = None

                    # Accelerator Pedal (INVERTED LOGIC)
                    accelerator_value = self.joystick.get_axis(ACCELERATOR_AXIS)
                    normalized_accel_for_speedometer = (accelerator_value + 1.0) / 2.0

                    if accelerator_value <= ACCELERATOR_THRESHOLD:
                        self.press_key(self.current_accelerator_key)
                        self.speedometer.target_speed = (1.0 - normalized_accel_for_speedometer) * MAX_SPEED
                    else:
                        self.release_key(self.current_accelerator_key)
                        self.speedometer.target_speed = (1.0 - normalized_accel_for_speedometer) * MAX_SPEED

                    # Get pedal values
                    brake_value = self.joystick.get_axis(BRAKE_AXIS)
                    clutch_value = self.joystick.get_axis(CLUTCH_AXIS)
                    
                    # Only print if values have changed significantly
                    if not hasattr(self, '_last_brake_value'):
                        self._last_brake_value = brake_value
                        self._last_clutch_value = clutch_value
                        print(f"Initial pedal values - Brake: {brake_value:.3f}, Clutch: {clutch_value:.3f}")
                    elif abs(brake_value - self._last_brake_value) > 0.01 or abs(clutch_value - self._last_clutch_value) > 0.01:
                        print(f"Pedal values changed - Brake: {brake_value:.3f}, Clutch: {clutch_value:.3f}")
                        self._last_brake_value = brake_value
                        self._last_clutch_value = clutch_value
                    
                    # Only use clutch pedal for 'E' key
                    clutch_pressed = clutch_value < -0.2
                    
                    # Trigger 'E' only with clutch pedal
                    if clutch_pressed:
                        if not self.simulated_states['e']:
                            print(f"Clutch pressed - 'E' key")
                            self.keyboard.press('e')
                            self.simulated_states['e'] = True
                    else:
                        if self.simulated_states['e']:
                            print(f"Clutch released - 'E' key")
                            self.keyboard.release('e')
                            self.simulated_states['e'] = False

                    # Button 13 for spacebar and brake indicator
                    button_13_down = self.joystick.get_button(13)
                    if button_13_down:
                        if not self.simulated_states[Key.space]:
                            print("Button 13 pressed - SPACEBAR")
                            self.keyboard.press(Key.space)
                            self.simulated_states[Key.space] = True
                    else:
                        if self.simulated_states[Key.space]:
                            print("Button 13 released - SPACEBAR")
                            self.keyboard.release(Key.space)
                            self.simulated_states[Key.space] = False
                    # Always update brake indicator based on button 13 state
                    self.gear_indicator.set_brake_indicator(button_13_down)
                    # Play handbrake sound on press (transition)
                    if button_13_down and not self._last_button_13:
                        if self.handbrake_sound:
                            self.handbrake_sound.play()
                    self._last_button_13 = button_13_down

                    # --- D-pad (Hat) Handling ---
                    if self.joystick.get_numhats() > DPAD_HAT_INDEX:
                        hat_value = self.joystick.get_hat(DPAD_HAT_INDEX)
                        # hat_value is (x, y) where x=-1 (left), 0 (center), 1 (right)
                        # and y=-1 (down), 0 (center), 1 (up)

                        if self.dpad_as_wasd:
                            # WASD mode
                            if hat_value[0] < 0:  # Left
                                self.press_key('a')
                            else:
                                self.release_key('a')
                            
                            if hat_value[0] > 0:  # Right
                                self.press_key('d')
                            else:
                                self.release_key('d')
                            
                            if hat_value[1] > 0:  # Up
                                self.press_key('w')
                            else:
                                self.release_key('w')
                            
                            if hat_value[1] < 0:  # Down
                                self.press_key('s')
                            else:
                                self.release_key('s')
                        else:
                            # Arrow/Cursor mode
                            if hat_value[0] < 0:  # Left
                                if not self.simulated_states[Key.left]:
                                    print("D-pad Left - Left Arrow")
                                    self.press_key(Key.left)
                            else:
                                if self.simulated_states[Key.left]:
                                    self.release_key(Key.left)
                            
                            if hat_value[0] > 0:  # Right
                                if not self.simulated_states[Key.right]:
                                    print("D-pad Right - Right Arrow")
                                    self.press_key(Key.right)
                            else:
                                if self.simulated_states[Key.right]:
                                    self.release_key(Key.right)
                            
                            if hat_value[1] != 0:  # Up or Down
                                screen_width, screen_height = pyautogui.size()
                                if hat_value[1] > 0:  # Up
                                    print("D-pad Up - Moving cursor to top center")
                                    pyautogui.moveTo(screen_width // 2, 0)  # Top center
                                else:  # Down
                                    print("D-pad Down - Moving cursor to bottom center")
                                    pyautogui.moveTo(screen_width // 2, screen_height)  # Bottom center

                except IndexError:
                    print(f"Error: Axis or Hat number out of range for joystick. Check your constants.")
                    self.joystick = None # Disable joystick polling
                except pygame.error as e:
                    print(f"Pygame input error: {e}")
                    self.joystick = None # Disable joystick polling

            time.sleep(0.01) # Small delay for input polling thread

    def stop(self):
        print("Stopping application...")
        self.running = False
        self.speedometer.running = False # Stop speedometer's update loop

        # Give the input polling thread a moment to finish
        if self.input_poll_thread.is_alive():
            self.input_poll_thread.join(timeout=0.1)

        # Release any potentially pressed simulated keys/buttons
        print("Releasing any potentially pressed simulated keys/buttons...")
        for state_name, is_pressed in self.simulated_states.items():
            if is_pressed:
                if state_name == 'lmb':
                    self.mouse.release(Button.left)
                elif state_name == 'rmb':
                    self.mouse.release(Button.right)
                elif state_name == 'ctrl_q':
                    self.keyboard.release('q')
                    self.keyboard.release(Key.ctrl_l)
                elif state_name == Key.space:
                    self.keyboard.release(Key.space)
                else:
                    self.keyboard.release(state_name)

        if pygame.joystick.get_init():
            pygame.joystick.quit()
        if pygame.get_init():
            pygame.quit()
        self.gear_window.destroy()  # Close the gear indicator window
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = G920MasterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.stop)
    root.mainloop()