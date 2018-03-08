# SchoolSoft (unofficial) API

## How do i initialize it?

Simple!

```python
api = SchoolSoft(school, username, password, usertype (optional))
```

## What does it do?

Currently pre-programmed calls are:

```python
api.fetch_lunch_menu()  # Gets the lunch menu and returns a list
api.fetch_schedule()    # Gets the schedule and returns a list
```

However, you can access almost any page by experimenting with:

```python
api.try_get(url)        # Runs a login call, and returns URL entered in request format
```
