"""
TeamAgent - Timski agent za strategiju
FIXED: Duži delay za registraciju vozača
"""

import asyncio
import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message
from spade.template import Template

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.race_config import RaceConfig


class TeamAgent(Agent):
    """Timski agent"""

    def __init__(self, jid, password, team_id):
        super().__init__(jid, password)
        self.team_id = team_id
        self.team_name = f"Team_{team_id}"

    class SendInitialStrategyBehaviour(OneShotBehaviour):
        async def run(self):
            # DUŽI DELAY - čekaj da se svi vozači registriraju!
            await asyncio.sleep(5)  # Povećano sa 0.5 na 5 sekundi

            chosen_strategy = RaceConfig.get_tire_strategy(self.agent.team_id)
            self.agent.log(f"Šaljem strategiju: {chosen_strategy.upper()}")

            for rider_id in self.agent.riders:
                rider_jid = f"rider_{rider_id}@{RaceConfig.XMPP_SERVER}"

                strategy = {
                    'type': 'initial_strategy',
                    'tire_compound': chosen_strategy,
                    'target_pace': 'moderate',
                    'overtake_aggression': 0.5
                }

                msg = Message(to=rider_jid)
                msg.set_metadata("performative", "inform")
                msg.set_metadata("ontology", "strategy")
                msg.body = json.dumps(strategy)

                await self.send(msg)
                self.agent.log(f"  ✓ Poslao Rider {rider_id}: {chosen_strategy}")

                # Mali delay između slanja
                await asyncio.sleep(0.2)

    class StrategyBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=1)

            if msg and msg.get_metadata("ontology") == "telemetry":
                try:
                    telemetry = json.loads(msg.body)
                    rider_id = telemetry['rider_id']
                    self.agent.telemetry_history.append(telemetry)

                    if telemetry['tire_wear'] > 0.7:
                        self.agent.log(f"⚠️  Rider {rider_id}: Wear {telemetry['tire_wear']:.1%}")

                except Exception as e:
                    self.agent.log(f"Greška: {e}")

            await asyncio.sleep(0.5)

    async def setup(self):
        self.log(f"Pokretanje...")

        self.telemetry_history = []
        self.riders = []
        self.num_riders = RaceConfig.NUM_RIDERS

        # Riders u timu
        for offset in [0, 1]:
            rider_id = self.team_id * 2 + offset
            if rider_id < RaceConfig.NUM_RIDERS:
                self.riders.append(rider_id)

        # Behaviours
        init_strategy = self.SendInitialStrategyBehaviour()
        self.add_behaviour(init_strategy)

        strategy_behaviour = self.StrategyBehaviour()
        template = Template()
        template.set_metadata("ontology", "telemetry")
        self.add_behaviour(strategy_behaviour, template)

    def log(self, message):
        print(f"[{self.team_name}] {message}")