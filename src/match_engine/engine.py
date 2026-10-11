from __future__ import annotations

import random
from dataclasses import asdict

from .model import EventType, MatchConfig, MatchEvent, MatchStats, Player, Team


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class MatchEngine:
    """Fixed-step, seeded state machine with a replayable event stream."""

    def __init__(self, home: Team, away: Team, config: MatchConfig | None = None):
        self.teams = [home, away]
        self.config = config or MatchConfig()
        self.rng = random.Random(self.config.seed)
        self.stats = [MatchStats(), MatchStats()]
        self.events: list[MatchEvent] = []
        self.possession = 0
        self.zone = 0.50  # perspective of team in possession: 0 own goal, 1 opponent goal
        self.lane = 0.50  # 0 left touchline, 1 right touchline
        self.carrier = self._pick_player(0, attacking=True)
        self.second = 0

    def _active(self, team: int) -> list[Player]:
        return [p for p in self.teams[team].players if not p.sent_off]

    def _pick_player(self, team: int, attacking: bool = False) -> Player:
        players = self._active(team)
        weights = []
        for player in players:
            weight = 1.0
            if attacking:
                weight += {"ST": 2.8, "W": 1.8, "CM": .8, "GK": -.8}.get(player.role, 0)
            weights.append(max(.1, weight))
        return self.rng.choices(players, weights=weights, k=1)[0]

    def _emit(
        self, kind: EventType, team: int | None = None, actor: Player | None = None,
        target_player: Player | None = None, **kw: object,
    ) -> None:
        kw.setdefault("x", self.zone)
        kw.setdefault("y", self.lane)
        kw.setdefault("team_index", team)
        kw.setdefault("player_ids", tuple(
            player.id for player in (actor, target_player) if player is not None
        ))
        if target_player is not None:
            kw.setdefault("target", target_player.name)
        self.events.append(MatchEvent(
            self.second, kind, self.teams[team].name if team is not None else None,
            actor.name if actor else None, **kw,
        ))

    def _turnover(self, reason: str, restart: EventType | None = None) -> None:
        old = self.possession
        self._emit(EventType.TURNOVER, old, self.carrier, detail=reason)
        self.possession = 1 - old
        self.zone = _clamp(1.0 - self.zone)
        self.lane = 1.0 - self.lane
        self.carrier = self._pick_player(self.possession)
        if restart is not None:
            self._emit(restart, self.possession, self.carrier, detail=reason,
                       important=restart in {EventType.CORNER, EventType.FREE_KICK})

    def _foul_check(self, defender: Player) -> bool:
        defending = 1 - self.possession
        tactics = self.teams[defending].tactics
        probability = .010 + .020 * tactics.pressing + .012 * (1 - defender.attribute("decisions"))
        if self.rng.random() >= probability:
            return False
        stats = self.stats[defending]
        stats.fouls += 1
        self._emit(EventType.FOUL, defending, defender, important=self.zone > .78)
        card_roll = self.rng.random()
        if card_roll < .18:
            if defender.yellow:
                defender.sent_off = True
                stats.reds += 1
                self._emit(EventType.RED, defending, defender, detail="second yellow", important=True)
            else:
                defender.yellow = True
                stats.yellows += 1
                self._emit(EventType.YELLOW, defending, defender, important=True)
        elif card_roll < .183:
            defender.sent_off = True
            stats.reds += 1
            self._emit(EventType.RED, defending, defender, detail="straight red", important=True)
        # A foul stops play but does not transfer possession. The restart is
        # represented separately, matching the observed match-event boundary.
        self._emit(EventType.FREE_KICK, self.possession, self.carrier,
                   detail="attacking third" if self.zone > .66 else "open play",
                   important=self.zone > .78)
        return True

    def _shot(self) -> None:
        team = self.possession
        shooter = self.carrier
        pressure = self.teams[1 - team].tactics.pressing
        distance_factor = _clamp((self.zone - .62) / .36)
        xg = _clamp(
            .008 + .105 * distance_factor
            + .030 * shooter.attribute("finishing") - .018 * pressure,
            .01, .32,
        )
        self.stats[team].shots += 1
        self.stats[team].xg += xg
        self._emit(EventType.SHOT, team, shooter, xg=xg, important=xg >= .10)
        goalkeeper = next((p for p in self._active(1 - team) if p.role == "GK"), self._pick_player(1 - team))
        goal_probability = xg * (
            .95 + .18 * (shooter.attribute("finishing") - goalkeeper.attribute("goalkeeping"))
        )
        goal = self.rng.random() < _clamp(goal_probability)
        on_target = goal or self.rng.random() < _clamp(
            .24 + .38 * shooter.attribute("finishing") - .12 * pressure
        )
        if on_target:
            self.stats[team].shots_on_target += 1
        if goal:
            self.stats[team].goals += 1
            self._emit(EventType.GOAL, team, shooter, xg=xg, important=True)
        else:
            self._emit(EventType.SAVE if on_target else EventType.MISS,
                       1 - team if on_target else team, goalkeeper if on_target else shooter,
                       xg=xg, important=xg >= .16)
        if self.stats[team].goals and self.events[-1].type == EventType.GOAL:
            self.possession = 1 - team
            self.zone, self.lane = .50, .50
            self.carrier = self._pick_player(self.possession)
            self._emit(EventType.KICK_OFF, self.possession, self.carrier, detail="after goal")
        elif on_target:
            self.possession = 1 - team
            self.zone, self.lane = .08, .50
            self.carrier = goalkeeper
        elif self.rng.random() < .22 + .18 * pressure:
            # Defender/keeper deflection: the attacking team keeps the ball.
            self.stats[team].corners += 1
            self.zone = .93
            self.lane = 0.02 if self.lane < .5 else .98
            self.carrier = self._pick_player(team, attacking=True)
            self._emit(EventType.CORNER, team, self.carrier, important=True)
        else:
            self.possession = 1 - team
            self.zone, self.lane = .06, .50
            self.carrier = goalkeeper
            self._emit(EventType.GOAL_KICK, self.possession, goalkeeper)

    def _step(self) -> None:
        team = self.possession
        attack = self.teams[team]
        defend = self.teams[1 - team]
        self.stats[team].possession_ticks += 1
        defender = self._pick_player(1 - team)
        if self._foul_check(defender):
            return

        t = attack.tactics
        # A tick is a decision opportunity, not an event guarantee. Keeping the
        # per-tick shot utility low prevents settled attacks from producing an
        # implausible attempt every few seconds.
        shot_urge = _clamp((self.zone - .70) * .34 + t.mentality * .025, 0, .16)
        if self.zone > .62 and self.rng.random() < shot_urge:
            self._shot()
            return

        carry_chance = _clamp(
            .20 + .22 * (1 - t.directness) + .14 * self.carrier.attribute("pace")
        )
        if self.rng.random() < carry_chance:
            advantage = self.config.home_advantage if team == 0 else -self.config.home_advantage
            contest = (
                .48 + .22 * self.carrier.attribute("pace") * self.carrier.energy
                - .20 * defender.attribute("tackling") * defender.energy + advantage
            )
            if self.rng.random() < _clamp(contest):
                gain = .018 + .035 * self.carrier.attribute("pace") * (1 + .25 * t.tempo)
                self.zone = _clamp(self.zone + gain)
                self.lane = _clamp(self.lane + self.rng.uniform(-.07, .07) * t.width)
                self._emit(EventType.CARRY, team, self.carrier)
            else:
                self._turnover("tackle")
            return

        receiver = self._pick_player(team, attacking=True)
        length = .025 + .09 * t.directness
        risk = length * (1 + defend.tactics.pressing) + max(0, self.zone - .72) * .10
        advantage = self.config.home_advantage if team == 0 else -self.config.home_advantage
        completion = _clamp(
            .66 + .29 * self.carrier.attribute("passing") * self.carrier.energy
            - risk + advantage
        )
        self.stats[team].passes += 1
        if self.rng.random() < completion:
            if self.zone > .72 and t.directness > .58 and self.rng.random() < .035 + .08 * defend.tactics.defensive_line:
                self._emit(EventType.OFFSIDE, team, receiver, important=self.zone > .84)
                self.stats[team].offsides += 1
                self._turnover("offside")
                return
            self.stats[team].completed_passes += 1
            self.zone = _clamp(
                self.zone + length * (.65 + .4 * receiver.attribute("decisions"))
            )
            self.lane = _clamp(self.lane + self.rng.uniform(-.16, .16) * t.width)
            self._emit(EventType.PASS, team, self.carrier, target_player=receiver)
            self.carrier = receiver
        else:
            self._turnover("interception")

        fatigue_rate = self.config.tick_seconds / 5400 * (1.15 + .45 * t.tempo + .35 * t.pressing)
        for player in self._active(team):
            player.fatigue = _clamp(
                player.fatigue + fatigue_rate * (1.05 - .45 * player.attribute("stamina")),
                0, .55,
            )

    def _added_time(self, start: int, end: int) -> int:
        """Deterministic approximation based on recorded stoppage events."""
        stoppages = sum(
            1 for event in self.events
            if start <= event.second < end and event.type in {
                EventType.GOAL, EventType.FOUL, EventType.YELLOW, EventType.RED,
            }
        )
        return min(5 * 60, (stoppages * 7 // 30) * 30)

    def run(self) -> dict[str, object]:
        self._emit(EventType.KICK_OFF, self.possession, important=True)
        half_length = self.config.seconds // 2
        for second in range(0, half_length, self.config.tick_seconds):
            self.second = second
            self._step()

        first_added = self._added_time(0, half_length)
        self.second = half_length
        self._emit(EventType.ADDED_TIME, detail=f"{first_added // 60} minutes")
        for second in range(half_length, half_length + first_added, self.config.tick_seconds):
            self.second = second
            self._step()

        self.second = half_length + first_added
        self._emit(EventType.HALF_TIME, important=True)
        self.possession = 1
        self.zone, self.lane = .50, .50
        self.carrier = self._pick_player(1)
        self._emit(EventType.KICK_OFF, 1, self.carrier, detail="second half")

        second_start = self.second
        second_end = second_start + (self.config.seconds - half_length)
        for second in range(second_start, second_end, self.config.tick_seconds):
            self.second = second
            self._step()
        second_added = self._added_time(second_start, second_end)
        self.second = second_end
        self._emit(EventType.ADDED_TIME, detail=f"{second_added // 60} minutes")
        for second in range(second_end, second_end + second_added, self.config.tick_seconds):
            self.second = second
            self._step()
        self.second = second_end + second_added
        self._emit(EventType.FULL_TIME, important=True)
        total_ticks = max(1, sum(s.possession_ticks for s in self.stats))
        return {
            "seed": self.config.seed,
            "duration": self.second,
            "setup": dict(self.config.setup),
            "input": {
                "home": self.teams[0].as_input_dict(),
                "away": self.teams[1].as_input_dict(),
            },
            "score": {self.teams[i].name: self.stats[i].goals for i in range(2)},
            "stats": {
                self.teams[i].name: {
                    **asdict(self.stats[i]),
                    "xg": round(self.stats[i].xg, 3),
                    "possession": round(100 * self.stats[i].possession_ticks / total_ticks, 1),
                } for i in range(2)
            },
            "events": [event.as_dict() for event in self.events],
            "highlights": self.highlight_windows(),
        }

    def highlight_windows(self, padding: int = 15) -> list[dict[str, int]]:
        important = [e.second for e in self.events if e.important]
        match_end = max(self.config.seconds, self.second)
        windows: list[list[int]] = []
        for moment in important:
            start, end = max(0, moment - padding), min(match_end, moment + padding)
            if windows and start <= windows[-1][1]:
                windows[-1][1] = max(windows[-1][1], end)
            else:
                windows.append([start, end])
        return [{"start": start, "end": end} for start, end in windows]
