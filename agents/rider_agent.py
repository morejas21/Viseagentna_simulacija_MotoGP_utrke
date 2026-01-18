"""
RiderAgent - Autonomni vozač agent
FIXED: Centralizirani position tracking
"""

import asyncio
import json
import random
from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message
from spade.template import Template
import numpy as np

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.race_config import RaceConfig


class RiderAgent(Agent):
    """Agent vozača"""

    def __init__(self, jid, password, rider_id):
        super().__init__(jid, password)
        self.rider_id = rider_id
        self.rider_name = f"Rider_{rider_id}"

    class StartState(State):
        async def run(self):
            self.agent.log(f"START - čekam strategiju...")

            msg = await self.receive(timeout=15)

            if msg and msg.get_metadata("ontology") == "strategy":
                try:
                    strategy = json.loads(msg.body)
                    self.agent.tire_compound = strategy.get('tire_compound', 'medium')
                    self.agent.log(f"✓ Primio: {self.agent.tire_compound} gume")
                except Exception as e:
                    self.agent.log(f"Greška: {e}")
                    self.agent.tire_compound = 'medium'
            else:
                self.agent.log("Timeout - default medium")
                self.agent.tire_compound = 'medium'

            self.agent.race_started = True
            self.agent.log("➡️ Prelazim u RACING stanje")
            self.set_next_state("RACING")

    class RacingState(State):
        async def run(self):
            # Provjera završetka
            if self.agent.current_lap >= RaceConfig.NUM_LAPS:
                self.agent.log("➡️ Završavam - prelazim u FINISH")
                self.set_next_state("FINISH")
                return

            # Simulacija kruga
            lap_time = self.agent.calculate_lap_time()
            self.agent.total_time += lap_time
            self.agent.current_lap += 1
            self.agent.update_tire_degradation()

            # Spremanje
            self.agent.lap_times.append(lap_time)
            self.agent.lap_data.append({
                'lap': self.agent.current_lap,
                'time': lap_time,
                'tire_wear': self.agent.tire_wear,
                'position': self.agent.current_position,
                'overtake': False
            })

            # Slanje lap update Coordinatoru (za position tracking)
            coordinator_jid = f"coordinator@{RaceConfig.XMPP_SERVER}"
            lap_update = {
                'type': 'lap_update',
                'rider_id': self.agent.rider_id,
                'lap': self.agent.current_lap,
                'total_time': self.agent.total_time,
                'tire_wear': self.agent.tire_wear
            }
            msg = Message(to=coordinator_jid)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("ontology", "lap_update")
            msg.body = json.dumps(lap_update)
            await self.send(msg)

            # Čekaj position update od Coordinatora
            pos_msg = await self.receive(timeout=0.5)
            if pos_msg and pos_msg.get_metadata("ontology") == "position_update":
                data = json.loads(pos_msg.body)
                old_pos = self.agent.current_position
                self.agent.current_position = data['position']

                # Log pretjecanja
                if old_pos > self.agent.current_position:
                    self.agent.log(f"  ✓ Pretjecanje → P{self.agent.current_position}")
                    self.agent.overtake_count += 1
                    self.agent.lap_data[-1]['overtake'] = True

            # Log svakih 5 krugova
            if self.agent.current_lap % 5 == 0:
                self.agent.log(f"Lap {self.agent.current_lap}/{RaceConfig.NUM_LAPS} "
                              f"- {lap_time:.2f}s, Wear: {self.agent.tire_wear:.1%}, "
                              f"P{self.agent.current_position}")

            # Telemetrija za Team
            if self.agent.current_lap % RaceConfig.TELEMETRY_INTERVAL == 0:
                team_jid = f"team_{self.agent.rider_id // 2}@{RaceConfig.XMPP_SERVER}"
                telemetry = {
                    'type': 'telemetry',
                    'rider_id': self.agent.rider_id,
                    'lap': self.agent.current_lap,
                    'tire_wear': self.agent.tire_wear,
                    'position': self.agent.current_position,
                    'avg_lap_time': float(np.mean(self.agent.lap_times[-3:])) if len(self.agent.lap_times) >= 3 else 0
                }
                msg = Message(to=team_jid)
                msg.set_metadata("performative", "inform")
                msg.set_metadata("ontology", "telemetry")
                msg.body = json.dumps(telemetry)
                await self.send(msg)

            self.set_next_state("RACING")
            await asyncio.sleep(RaceConfig.SIMULATION_DELAY)

    class FinishState(State):
        async def run(self):
            self.agent.log(f"🏁 FINISH - {self.agent.total_time:.2f}s, P{self.agent.current_position}")
            self.agent.race_finished = True

            # Slanje rezultata
            coordinator_jid = f"coordinator@{RaceConfig.XMPP_SERVER}"
            results = {
                'type': 'race_results',
                'rider_id': self.agent.rider_id,
                'total_time': self.agent.total_time,
                'final_position': self.agent.current_position,  # ← FIXED: Koristi real-time poziciju
                'tire_compound': self.agent.tire_compound,
                'overtakes': self.agent.overtake_count,
                'avg_lap_time': float(np.mean(self.agent.lap_times)),
                'lap_time_std': float(np.std(self.agent.lap_times)),
                'skill_level': self.agent.skill_level,
                'aggression': self.agent.aggression,
                'consistency': self.agent.consistency,
                'tire_wear_final': self.agent.tire_wear,
                'lap_data': self.agent.lap_data
            }
            msg = Message(to=coordinator_jid)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("ontology", "results")
            msg.body = json.dumps(results)
            await self.send(msg)

            await asyncio.sleep(1)

    async def setup(self):
        self.log(f"Pokretanje...")

        # State
        self.current_lap = 0
        self.total_time = 0.0
        self.tire_compound = 'medium'
        self.tire_wear = 0.0
        self.current_position = self.rider_id + 1
        self.race_started = False
        self.race_finished = False
        self.lap_times = []
        self.lap_data = []
        self.overtake_count = 0

        # Karakteristike
        self.aggression = random.uniform(*RaceConfig.AGGRESSION_RANGE)
        self.consistency = random.uniform(*RaceConfig.CONSISTENCY_RANGE)
        self.skill_level = random.uniform(*RaceConfig.SKILL_RANGE)

        self.log(f"Skill:{self.skill_level:.2f} Aggr:{self.aggression:.2f} Cons:{self.consistency:.2f}")

        # FSM
        fsm = FSMBehaviour()
        fsm.add_state(name="START", state=self.StartState(), initial=True)
        fsm.add_state(name="RACING", state=self.RacingState())
        fsm.add_state(name="FINISH", state=self.FinishState())

        fsm.add_transition(source="START", dest="RACING")
        fsm.add_transition(source="RACING", dest="RACING")
        fsm.add_transition(source="RACING", dest="FINISH")

        self.add_behaviour(fsm)

    def calculate_lap_time(self):
        tire_config = RaceConfig.TIRE_COMPOUNDS[self.tire_compound]
        base_time = RaceConfig.LAP_BASE_TIME / tire_config['base_speed']
        degradation_penalty = self.tire_wear * 5.0
        skill_factor = (2.0 - self.skill_level) * 2.0
        consistency_noise = random.gauss(0, (1 - self.consistency) * 2.0)
        lap_time = base_time + degradation_penalty + skill_factor + consistency_noise
        return max(lap_time, 80.0)

    def update_tire_degradation(self):
        tire_config = RaceConfig.TIRE_COMPOUNDS[self.tire_compound]
        base_degradation = tire_config['degradation_rate']
        aggression_factor = 1.0 + (self.aggression * 0.5)
        self.tire_wear += base_degradation * aggression_factor
        self.tire_wear = min(self.tire_wear, 1.0)

    def log(self, message):
        print(f"[{self.rider_name}] {message}")