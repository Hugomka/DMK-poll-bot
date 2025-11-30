from datetime import datetime, date

import pytz


class TimeZoneHelper:
    """Hulpfunctie voor tijdzone-conversies en Hammertime generatie."""

    @staticmethod
    def nl_tijd_naar_hammertime(
        datum_str: str, tijd_str: str, style: str = "t"
    ) -> str:
        """Converteer Nederlandse datum/tijd naar Discord Hammertime.

        Args:
            datum_str: Datum in YYYY-MM-DD formaat
            tijd_str: Tijd in HH:MM formaat
            style: Hammertime style ('t', 'T', 'd', 'D', 'f', 'F', 'R')

        Returns:
            Hammertime string (bijv. "<t:1234567890:t>")
        """
        try:
            nl_tz = pytz.timezone("Europe/Amsterdam")
            naive = datetime.strptime(f"{datum_str} {tijd_str}", "%Y-%m-%d %H:%M")
            localized = nl_tz.localize(naive)
            utc = localized.astimezone(pytz.UTC)
            timestamp = int(utc.timestamp())
            return f"<t:{timestamp}:{style}>"
        except Exception:
            # Fallback: toon gewoon de tijd als tekst
            return tijd_str

    @staticmethod
    def nl_tijd_naar_user_tijd(
        tijd_str: str, user_timezone: str = "Europe/Amsterdam", datum: date | None = None
    ) -> str:
        """Converteer Nederlandse tijd naar de tijdzone van de gebruiker.

        Args:
            tijd_str: Tijd in HH:MM formaat (Nederlandse tijd)
            user_timezone: Tijdzone van gebruiker (bijv. "America/New_York")
            datum: Datum voor DST berekening (standaard: vandaag)

        Returns:
            Tijd string in gebruiker tijdzone (bijv. "13:00")
        """
        try:
            nl_tz = pytz.timezone("Europe/Amsterdam")
            user_tz = pytz.timezone(user_timezone)

            # Gebruik opgegeven datum of vandaag voor correcte DST
            if datum is None:
                datum = date.today()

            tijd_obj = datetime.strptime(tijd_str, "%H:%M").time()
            naive = datetime.combine(datum, tijd_obj)

            localized = nl_tz.localize(naive)
            user_time = localized.astimezone(user_tz)
            return user_time.strftime("%H:%M")
        except Exception:
            # Fallback: toon originele NL tijd
            return tijd_str
