import re

def nmea_to_coords(nmea_sentence, default_alt=10):
    """
    Convert NMEA sentence to [lat, lon, alt].
    Supports GPGGA and GPRMC sentences.
    Returns None if parsing fails.
    """
    try:
        if nmea_sentence.startswith('$GPGGA'):
            # Example: $GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47
            parts = nmea_sentence.split(',')
            lat = float(parts[2][:2]) + float(parts[2][2:]) / 60  # DDMM.MMMM → Decimal degrees
            if parts[3] == 'S':
                lat *= -1
            lon = float(parts[4][:3]) + float(parts[4][3:]) / 60   # DDDMM.MMMM → Decimal degrees
            if parts[5] == 'W':
                lon *= -1
            return [round(lat, 6), round(lon, 6), default_alt]
        
        elif nmea_sentence.startswith('$GPRMC'):
            # Example: $GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A
            parts = nmea_sentence.split(',')
            lat = float(parts[3][:2]) + float(parts[3][2:]) / 60
            if parts[4] == 'S':
                lat *= -1
            lon = float(parts[5][:3]) + float(parts[5][3:]) / 60
            if parts[6] == 'W':
                lon *= -1
            return [round(lat, 6), round(lon, 6), default_alt]
        
    except (IndexError, ValueError, AttributeError):
        pass
    return None  # Failed to parse
