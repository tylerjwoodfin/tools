# SFPL DIY Digi Lab appointments

Emails me when the [SFPL DIY Digital Archive Lab](https://sfpl.libcal.com/appointments/diydigilab) has an open appointment.

- `main.py` reads the LibCal widget endpoints (`staff`, `datetime`, `times`) behind the booking page and emails one message listing timeslots it has not emailed before.
- Sent start times live in Cabinet `sfpl_digilab.sent`. Each run first drops entries more than 48 hours in the past.
- A slot is recorded only after the email sends, so a failed email retries next run.

## Cron

```
0 */3 * * * python3 /home/tyler/git/tools/sfpl_digilab/main.py
```

## Tests

```
cd sfpl_digilab && python3 -m unittest test_main
```
