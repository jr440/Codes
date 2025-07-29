import os
import time
import requests
import smtplib
import ssl
import threading # For running the Tkinter GUI in a separate thread
import tkinter as tk # For the graphical alarm window
from tkinter import messagebox # For simple message boxes if needed

# --- Configuration ---
DISHY_IP = "192.168.100.1"
CHECK_INTERVAL_SECONDS = 10 # How often to check the dish status

# Email Notification Settings (Uncomment and fill these if you want email alerts)
# You'll need to enable "Less secure app access" or generate an "App password" for Gmail,
# or use your email provider's specific instructions.
# EMAIL_SENDER = "your_email@example.com"
# EMAIL_PASSWORD = "your_email_password_or_app_password"
# EMAIL_RECEIVER = "your_phone_number@txt.att.net" # Example for SMS gateway, or another email
# EMAIL_SMTP_SERVER = "smtp.gmail.com"
# EMAIL_SMTP_PORT = 587 # Typically 587 for TLS, or 465 for SSL

# Pushbullet Notification Settings (Uncomment and fill these if you want Pushbullet alerts)
# You'll need to install 'pushbullet.py' (pip install pushbullet.py) and get your API key.
# from pushbullet import Pushbullet
# PUSHBULLET_API_KEY = "YOUR_PUSHBULLET_API_KEY"
# pb = Pushbullet(PUSHBULLET_API_KEY)

# --- Global Variables for GUI ---
alarm_window = None
alarm_state = False
flash_color_index = 0
flash_colors = ["red", "black"] # Colors for flashing alarm

# --- Notification Functions ---

def display_on_screen(message):
    """Prints messages to console, which will appear on your touchscreen terminal."""
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

# --- Visual Alarm Functions (Tkinter) ---

def dismiss_alarm():
    """Closes the alarm window and resets alarm state."""
    global alarm_window, alarm_state
    if alarm_window:
        alarm_window.destroy()
        alarm_window = None
    alarm_state = False
    display_on_screen("Alarm dismissed.")

def flash_background():
    """Changes the background color of the alarm window to create a flashing effect."""
    global alarm_window, flash_color_index
    if alarm_window and alarm_state:
        current_color = flash_colors[flash_color_index]
        alarm_window.config(bg=current_color)
        flash_color_index = (flash_color_index + 1) % len(flash_colors)
        alarm_window.after(500, flash_background) # Flash every 500ms (0.5 seconds)

def show_visual_alarm(alert_message):
    """Creates and displays a flashing, full-screen alarm window."""
    global alarm_window, alarm_state, flash_color_index

    if alarm_state: # Alarm already active, don't create new window
        return

    alarm_state = True
    flash_color_index = 0 # Reset flash color

    # Create the main window for the alarm
    alarm_window = tk.Tk()
    alarm_window.title("STARLINK ALERT!")
    
    # Make it fullscreen and always on top for maximum attention
    alarm_window.attributes('-fullscreen', True)
    alarm_window.attributes('-topmost', True)
    alarm_window.config(bg=flash_colors[0]) # Initial background color

    # Create a label for the message
    message_label = tk.Label(
        alarm_window,
        text=alert_message,
        font=("Inter", 48, "bold"), # Using Inter font as per guidelines, large size
        fg="white", # Text color
        bg=flash_colors[0], # Background color, will change with flashing
        wraplength=alarm_window.winfo_screenwidth() - 100 # Wrap text to fit screen
    )
    message_label.pack(expand=True, fill="both")

    # Create a dismiss button
    dismiss_button = tk.Button(
        alarm_window,
        text="DISMISS ALARM",
        font=("Inter", 24, "bold"),
        bg="green", # Green button
        fg="white",
        command=dismiss_alarm,
        relief="raised", # Raised button effect
        bd=5, # Border width
        padx=20, # Padding
        pady=10,
        width=20, # Fixed width for consistency
        height=2 # Fixed height
    )
    dismiss_button.pack(pady=50) # Padding below the button

    # Start the flashing effect
    flash_background()

        # Let's try this: The alarm window is a transient pop-up.
    alarm_window.protocol("WM_DELETE_WINDOW", dismiss_alarm) # Handle close button
    alarm_window.mainloop() # This will block until the window is closed

# --- Starlink Monitoring Functions ---

def check_dish_ping(ip_address):
    """Checks if the Starlink dish IP is reachable via ping."""
    # -c 1: send 1 packet
    # -W 1: wait 1 second for response
    # -q: quiet output
    # > /dev/null 2>&1: redirect all output to nowhere
    response = os.system(f"ping -c 1 -W 1 {ip_address} > /dev/null 2>&1")
    return response == 0 # Returns True if ping was successful (exit code 0)

def get_dish_status_json(ip_address):
    """Attempts to fetch basic status JSON from the dish's internal web server."""
    try:
        response = requests.get(f"http://{ip_address}/DishyStatus", timeout=5)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        # display_on_screen(f"Error fetching DishyStatus: {e}") # Uncomment for debugging
        return None

# --- Main Monitoring Loop ---

def monitor_starlink():
    """Main function to monitor Starlink status."""
    global alarm_state # Access global alarm state

    display_on_screen("Starlink Monitor started.")
    display_on_screen(f"Checking dish at {DISHY_IP} every {CHECK_INTERVAL_SECONDS} seconds.")

    dish_online_previous_state = False
    dish_status_previous = None

    try:
        while True:
            dish_online_current_state = check_dish_ping(DISHY_IP)
            current_dish_status = get_dish_status_json(DISHY_IP)

            if dish_online_current_state:
                if not dish_online_previous_state:
                    display_on_screen("Starlink Dish is now ONLINE.")
                    send_email_alert("Starlink Alert", "Starlink Dish is back online!")
                    send_pushbullet_alert("Starlink Online", "Your Starlink dish is now online.")
                    # If it just came online, ensure alarm is dismissed
                    if alarm_state:
                        dismiss_alarm()

                # Process current_dish_status if available
                if current_dish_status:
                    # You can parse specific values here if you want
                    # For example, to check if it's currently stowed or has errors
                    # if current_dish_status.get("stowed") == True:
                    #     display_on_screen("Dishy is stowed.")
                    pass # Placeholder for more detailed status processing

            else: # Dish is offline
                if dish_online_previous_state:
                    display_on_screen("WARNING: Starlink Dish has gone OFFLINE!")
                    send_email_alert("Starlink CRITICAL Alert", "WARNING: Starlink Dish has gone OFFLINE! Check connection or if moved.")
                    send_pushbullet_alert("Starlink Offline!", "WARNING: Your Starlink dish has gone offline!")
                    # Trigger the visual alarm
                    # Tkinter GUI operations must be in the main thread.
                    # We need to signal the main thread to show the alarm.
                    # For simplicity, we'll make a direct call, but it's better
                    # to use a queue for thread-safe communication in complex apps.
                    # For a simple alarm that pops up and blocks until dismissed, this is okay.
                    # If we want the monitoring to continue while alarm is shown,
                    # we need a more advanced threading model or a Tkinter-based main loop.

                    # Let's make the show_visual_alarm function run in a new thread
                    # to not block the monitoring loop, but be aware of Tkinter's
                    # non-thread-safe nature for updates *within* the Tkinter thread.
                    # The initial creation is usually fine.
                    if not alarm_state: # Only show if not already showing
                        alarm_thread = threading.Thread(target=show_visual_alarm, args=("STARLINK OFFLINE! Check Dish!",))
                        alarm_thread.daemon = True # Allow main program to exit even if thread is running
                        alarm_thread.start()


            dish_online_previous_state = dish_online_current_state
            dish_status_previous = current_dish_status # Keep track of status for future comparisons

            time.sleep(CHECK_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        display_on_screen("Starlink Monitor stopped by user.")
    except Exception as e:
        display_on_screen(f"An unexpected error occurred in monitoring: {e}")
        send_email_alert("Starlink Monitor Error", f"An unexpected error occurred: {e}")
        send_pushbullet_alert("Monitor Error", f"An unexpected error occurred: {e}")
        # Also show a visual alarm for critical errors
        if not alarm_state:
            alarm_thread = threading.Thread(target=show_visual_alarm, args=(f"MONITOR ERROR: {e}",))
            alarm_thread.daemon = True
            alarm_thread.start()
    finally:
        display_on_screen("Exiting Starlink Monitor.")
        # Ensure alarm is dismissed on exit
        if alarm_window:
            alarm_window.quit() # Properly quit Tkinter mainloop if running

if __name__ == "__main__":
    # Start the monitoring in a separate thread
    monitor_thread = threading.Thread(target=monitor_starlink)
    monitor_thread.daemon = True # Allow main program to exit even if thread is running
    monitor_thread.start()

    
    root = tk.Tk()
    root.withdraw() # Hide the main root window

    # Queue for messages from monitoring thread to GUI thread
    import queue
    gui_queue = queue.Queue()

    # Function to check the queue and update GUI
    def check_gui_queue():
        try:
            while True:
                callback = gui_queue.get_nowait()
                callback()
        except queue.Empty:
            pass
        finally:
            root.after(100, check_gui_queue) # Check every 100ms

    # Modified show_visual_alarm to be called by the main thread
    def show_visual_alarm_thread_safe(alert_message):
        global alarm_window, alarm_state, flash_color_index
        if alarm_state:
            return

        alarm_state = True
        flash_color_index = 0

        alarm_window = tk.Toplevel(root) # Use Toplevel for pop-up
        alarm_window.title("STARLINK ALERT!")
        alarm_window.attributes('-fullscreen', True)
        alarm_window.attributes('-topmost', True)
        alarm_window.config(bg=flash_colors[0])

        message_label = tk.Label(
            alarm_window,
            text=alert_message,
            font=("Inter", 48, "bold"),
            fg="white",
            bg=flash_colors[0],
            wraplength=root.winfo_screenwidth() - 100
        )
        message_label.pack(expand=True, fill="both")

        dismiss_button = tk.Button(
            alarm_window,
            text="DISMISS ALARM",
            font=("Inter", 24, "bold"),
            bg="green",
            fg="white",
            command=dismiss_alarm_thread_safe, # Use thread-safe dismiss
            relief="raised",
            bd=5,
            padx=20,
            pady=10,
            width=20,
            height=2
        )
        dismiss_button.pack(pady=50)

        # Start flashing only if the window exists
        alarm_window.after(500, flash_background_thread_safe)
        alarm_window.protocol("WM_DELETE_WINDOW", dismiss_alarm_thread_safe)

    def dismiss_alarm_thread_safe():
        global alarm_window, alarm_state
        if alarm_window:
            alarm_window.destroy()
            alarm_window = None
        alarm_state = False
        display_on_screen("Alarm dismissed.")

    def flash_background_thread_safe():
        global alarm_window, flash_color_index
        if alarm_window and alarm_state:
            current_color = flash_colors[flash_color_index]
            alarm_window.config(bg=current_color)
            flash_color_index = (flash_color_index + 1) % len(flash_colors)
            alarm_window.after(500, flash_background_thread_safe)

    # Modified monitor_starlink to put alarm calls into the queue
    def monitor_starlink_threaded():
        global alarm_state
        display_on_screen("Starlink Monitor started in background thread.")
        display_on_screen(f"Checking dish at {DISHY_IP} every {CHECK_INTERVAL_SECONDS} seconds.")

        dish_online_previous_state = False
        dish_status_previous = None

        try:
            while True:
                dish_online_current_state = check_dish_ping(DISHY_IP)
                current_dish_status = get_dish_status_json(DISHY_IP)

                if dish_online_current_state:
                    if not dish_online_previous_state:
                        display_on_screen("Starlink Dish is now ONLINE.")
                        send_email_alert("Starlink Alert", "Starlink Dish is back online!")
                        send_pushbullet_alert("Starlink Online", "Your Starlink dish is now online.")
                        if alarm_state:
                            gui_queue.put(dismiss_alarm_thread_safe) # Signal GUI to dismiss

                    if current_dish_status:
                        pass # Process detailed status if needed

                else: # Dish is offline
                    if dish_online_previous_state:
                        display_on_screen("WARNING: Starlink Dish has gone OFFLINE!")
                        send_email_alert("Starlink CRITICAL Alert", "WARNING: Starlink Dish has gone OFFLINE! Check connection or if moved.")
                        send_pushbullet_alert("Starlink Offline!", "WARNING: Your Starlink dish has gone offline!")
                        if not alarm_state:
                            gui_queue.put(lambda: show_visual_alarm_thread_safe("STARLINK OFFLINE! Check Dish!"))

                dish_online_previous_state = dish_online_current_state
                dish_status_previous = current_dish_status

                time.sleep(CHECK_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            display_on_screen("Starlink Monitor stopped by user (via console).")
            # If mainloop is running, it will eventually exit
        except Exception as e:
            display_on_screen(f"An unexpected error occurred in monitoring: {e}")
            send_email_alert("Starlink Monitor Error", f"An unexpected error occurred: {e}")
            send_pushbullet_alert("Monitor Error", f"An unexpected error occurred: {e}")
            if not alarm_state:
                gui_queue.put(lambda: show_visual_alarm_thread_safe(f"MONITOR ERROR: {e}"))
        finally:
            display_on_screen("Background monitoring thread exiting.")


    # Start the monitoring in a separate thread
    monitor_thread = threading.Thread(target=monitor_starlink_threaded)
    monitor_thread.daemon = True # Allows main thread to exit even if this is running
    monitor_thread.start()

    # Start checking the queue for GUI updates
    check_gui_queue()

    # Run the Tkinter main loop in the main thread
    root.mainloop()
