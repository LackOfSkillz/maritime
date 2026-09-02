# The Sailor's Handbook

Two halves. The first is for anybody aboard a ship; the second is for anybody putting ships
into a game.

These are the same files whether you are reading them on the web, in the ship's own
interface, or in the repository — one set of words, so they cannot disagree with each other.

---

# Part one: sailing her

Ordered the way you would learn it, not alphabetically.

## Getting about

1. **[Under way](under-way.md)** — casting off, the helm, and taking the way off her
2. **[Sailing](sailing.md)** — the wind, the points of sailing, and how much canvas to set
3. **[Oars](oars.md)** — for craft that are pulled rather than sailed
4. **[Navigation](navigation.md)** — where you are, where you think you are, and the
   difference between the two
5. **[Soundings and the ground](soundings.md)** — the lead, shoal water, and getting off
   again when you get it wrong
6. **[Harbours](harbours.md)** — coming alongside, letting go, and being taken there for you

## Seeing

7. **[The lookout](lookout.md)** — what is in sight, and what you can tell about it

## Fighting

8. **[The guns](guns.md)** — serving them, laying them, and choosing what to load
9. **[Ramming](ramming.md)** — running one hull into another, and what it costs you
10. **[Boarding](boarding.md)** — grapples, carrying a deck, and striking your colours

## The ship herself

11. **[Her people](crew.md)** — the company, what they are worth, and what they will take
12. **[Cargo](cargo.md)** — loading, discharging, and what a full hold does to her

## On land

13. **[Ashore](ashore.md)** — the town, the counters, and walking about
14. **[The interface](interface.md)** — the panel, the chart, the map, and the switches

---

# Part two: building with it

**You do not have to take all of this.** A game that wants a ferry between two islands takes
two layers and stops, and that is not a compromise — it is what the layers are for.

15. **[For developers](for-developers.md)** — the layers, and which ones you actually need
16. **[Putting it in an existing game](integrating.md)** — four steps, none of which touch a
    file outside your own game
17. **[Taking only part of it](adopting-a-part.md)** — the ferry, the rowing boat, the
    trader: four worked recipes with the rest left out
18. **[Your own coast](your-own-world.md)** — seabed, weather, currents, tides and marks
19. **[Your own ships](your-own-ships.md)** — hulls, rigs, guns and crews
20. **[Rooms and typeclasses](rooms-and-typeclasses.md)** — what to mix into your own rooms
21. **[Hooking into it](extending.md)** — narration, ownership, and the decisions left to you

## Reference

22. **[Every command](commands.md)** — grouped by what you are trying to do
23. **[Every setting](settings.md)** — grouped the same way

---

## A word on how to read part one

Orders are given as they were given: you say a thing, somebody answers, and then it
happens — or it does not, and somebody tells you why. Nothing aboard is instant. A ship
takes time to come round, a gun takes time to run out, and a crew takes time to do what they
are told and longer if they are frightened.

If a command refuses, read the refusal. It is nearly always the answer.

## And on part two

Three rules the whole contrib follows, which are worth knowing before you read any of it:

- **Nothing outside your own game directory is edited.**
- **Absence is not an error.** A hull with no measured length, a ship with no crew, a world
  with no weather — every one is a legitimate state with sensible behaviour, and that is
  what makes partial adoption safe.
- **Your game's decisions stay yours.** What a ship is worth, what a cargo sells for, what
  being cold in the water does to a person — the contrib has no opinion, because those
  collide with whatever you already have.
