# Putting it in an existing game

[Back to the handbook](index.md) · [For developers](for-developers.md)

**Nothing outside your own game directory is edited.** No file inside Evennia is touched, no
core class is subclassed, and no migration is needed. If a step here ever asks you to edit
something in `evennia/`, that is a bug in this page.

There are four steps. The first is required; you can stop after any of the rest.

---

## 1. Start the driver

**Once per game, or nothing moves.** There is no `INSTALLED_APPS` entry to add — this is a
contrib, not a Django application, and it has no models and no migrations. What it has is a
scheduler, and something has to start it:

```python
from evennia.utils import create
from evennia.contrib.full_systems.maritime.scripts import MaritimeDriver

create.create_script(MaritimeDriver)
```

Run that once, from a shell or a batch file. It is the single step people miss, and the
symptom is a ship that accepts every order and never goes anywhere.

Requires Evennia 6.1 or later. There is nothing to `pip install`.

## 2. Put the commands somewhere

A ship's rooms carry the helm. In your `at_object_creation`, or in the builder that makes
her:

```python
from evennia.contrib.full_systems.maritime import HelmCmdSet

deck.cmdset.add(HelmCmdSet, persistent=True)
```

And the builder's tool on your character class, because a world is built from dry land:

```python
from evennia.contrib.full_systems.maritime import ShipwrightCmdSet

class Character(DefaultCharacter):
    def at_object_creation(self):
        super().at_object_creation()
        self.cmdset.add(ShipwrightCmdSet, persistent=True)
```

Only want some of them? See [taking only part of it](adopting-a-part.md).

## 3. Describe your coast

Optional. Without it she sails on a flat sea two hundred metres deep, which is fine for a
ferry and useless for a game about rocks.

```python
MARITIME_MAP_PROVIDER = "world.sea.MyCoast"
MARITIME_WEATHER_PROVIDER = "world.sea.MyWeather"
MARITIME_TIDE_PROVIDER = "world.sea.MyTide"
```

See [your own coast](your-own-world.md).

## 4. The graphical panel

Optional, and it is the only step with any markup in it.

- Add the contrib's static directory to `STATICFILES_DIRS`. Contribs are not Django apps,
  so their static files are not otherwise found:

  ```python
  import os
  from evennia.contrib.full_systems import maritime

  STATICFILES_DIRS += [os.path.join(os.path.dirname(maritime.__file__), "web", "static")]
  ```

- Override `webclient/webclient.html` in your own templates directory. Evennia's is about
  twenty-five lines and already exposes an empty `{% block scripts %}`, so your override adds
  a mount point, a few script tags and a stylesheet, and inherits the rest:

  ```html
  {% extends "webclient/base.html" %}
  {% block scripts %}
    {{ block.super }}
    <div id="maritime-root"></div>
    <link rel="stylesheet" href="{% static 'maritime/maritime.css' %}">
    <link rel="stylesheet" href="{% static 'maritime/maritime-layout.css' %}">
    <script src="{% static 'maritime/maritime-state.js' %}"></script>
    <script src="{% static 'maritime/maritime-chart.js' %}"></script>
    <script src="{% static 'maritime/maritime-landmap.js' %}"></script>
    <script src="{% static 'maritime/maritime-panels.js' %}"></script>
    <script src="{% static 'maritime/maritime-ui.js' %}"></script>
    <script src="{% static 'maritime/maritime-transport.js' %}"></script>
  {% endblock %}
  ```

  `maritime-layout.css` is separable. It turns the webclient into a full-window bridge while
  somebody is aboard, and every rule in it is scoped to `:root:has(#maritime-root.maritime-on)`
  — so leaving it out keeps the webclient you already have, and putting it in gives the
  screen back the moment a player steps ashore.

- Let a browser announce itself:

  ```python
  INPUT_FUNC_MODULES += ["evennia.contrib.full_systems.maritime.client.inputfuncs"]
  ```

  Skip this and everything else still works; the game simply never learns which of its
  sessions are graphical.

- `evennia collectstatic`.

**The handbook comes with it.** Once the static files are collected, this manual is served
at `/static/maritime/help.html`, the panel has a `?` in its top right that opens it, and
`maritime help` prints the address. To make that address a full URL rather than a path,
set:

```python
WEBSERVER_HOSTNAME = "https://yourgame.example"
```

---

## What a player sees at each step

| After step | Aboard | Ashore |
| --- | --- | --- |
| 1 | Ships move, when something tells them to; no commands | Nothing |
| 2 | The full helm, in text | Nothing |
| 3 | Real depth under her, real weather | Nothing |
| 4 | The panel: chart, instruments, controls | Your own game, unchanged |

Stepping ashore hands the screen back to your game by default. If your game *is* a coast and
you want the panel to stay up with a town map on it:

```python
MARITIME_ASHORE_PANEL = True
```

---

Next: **[Taking only part of it](adopting-a-part.md)** or
**[Your own coast](your-own-world.md)**.
