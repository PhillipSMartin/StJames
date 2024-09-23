from datetime import datetime
import pytz


# Get date and time from the console
date_str = input("Enter the date (YYYY-MM-DD): ")
time_str = input("Enter the time (HH:MM AM/PM): ")

# Combine date and time strings
datetime_str = f"{date_str} {time_str}"

# Parse the datetime string
dt = datetime.strptime(datetime_str, "%Y-%m-%d %I:%M %p")

# Set the timezone to Eastern Time
eastern = pytz.timezone('US/Eastern')
dt_with_tz = eastern.localize(dt)

# Convert to UTC
utc_time = dt_with_tz.astimezone(pytz.UTC)

# Convert to Unix epoch time
epoch_time = int(utc_time.timestamp())

print( epoch_time )


# Convert epoch time to datetime object
utc_time = datetime.utcfromtimestamp(epoch_time)

# Set the timezone to UTC
utc_time = utc_time.replace(tzinfo=pytz.UTC)

# Convert to New York time
new_york_tz = pytz.timezone('America/New_York')
new_york_time = utc_time.astimezone(new_york_tz)

print(new_york_time.strftime("%Y-%m-%d %I:%M %p"))
