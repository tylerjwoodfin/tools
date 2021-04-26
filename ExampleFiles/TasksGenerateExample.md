This is an example of your TextGenerate.md:
```
[mon] This task is added if today is Monday.
[thu] This task is added if today is Thursday.
[D01] This task is added if today is the 1st of the month.
[D31] This task is added if today is the 31st of the month.
[12-31] This task is added if today is December 31.
[1-5] This task is added if today is January 5. (not tested on non-US systems)
[M%2] This task is added if today is the first day of an even-numbered month (try other modulo examples: https://www.wolframalpha.com/input/?i=6%252)
[W%3] This task is added if today is a Sunday of every third week, based on Epoch Time. See instructions below...
[D%4] This task is added every 4 days.
[W%3+1] This task is added if today is a Sunday of every third week, _with an offset of 1_, meaning if [W%3] would normally be added last week, it will be added this week instead.
```

Bad Examples:
```
[Monday] You must use sun, mon, tue, wed, thu, fri, or sat. Capitalization doesn't matter.
[D50] Months only have up to 31 days.
[Y%5] Year is unsupported.
(thu) You must use brackets.
{thu} You must use brackets.
  [W%3] You must start tasks on the first column.
[W%3-1] This is invalid. To add an offset, you MUST use +.
[W%3+4] This is also invalid. An offset of 4 makes no sense because [W%3+1] offsets 1 week, [W%3+2] offsets 2 weeks, and [W%3+3] is the same thing as [W%3]. [W%3+4] is the same as [W%3+1].
```

# How to use, assuming Linux:
- type "crontab -e" in the terminal

- Add the line below (without the >, without the #, replacing the path with your real path):
> 0 * * * * python3 path/to/tasks.py generate


# Epoch Time and working with "every n weeks", "every n days", "every n months":
- The Epoch time is the number of seconds since January 1, 1970, UTC.
- For example, if the current time is 1619394350, then today is Sunday, April 25, 2021 at 11:45:50PM UTC.
- The "week number" is calculated by {epochTime}/60/60/24/7.
    - 1619394350 /60/60/24/7 ~= 2677
    - 2677 % 3 == 1, meaning scheduling a task for [W%3] would be added last week, but not this week (or next week or the week after).