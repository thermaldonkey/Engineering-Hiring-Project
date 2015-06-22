def format_date(date):
    """
    Returns given date as a string in the format YYYY-MM-DD.

    @param date (datetime.date): The date to format
    @return (str): date formatted as a YYYY-MM-DD string
    """
    return date.strftime('%Y-%m-%d')

