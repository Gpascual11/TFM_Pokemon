import asyncio
import uuid
import os
import pandas as pd
from tqdm import tqdm
from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.player import DoubleBattleOrder

# Import both heuristics from v1 and v2 scripts (same folder).
from testing_heuristic_v1 import TFMExpertDoubles as TFMExpertDoublesV1
from testing_heuristic_v2 import TFMExpertDoubles as TFMExpertDoublesV2


def _extract_results(player, player_label, opponent_label):
    """Convert finished battles from a player into rows with heuristic winner labels."""
    rows = []
    for bid, b in player.battles.items():
        if not b.finished:
            continue
        if b.won:
            winner = player_label
        elif b.lost:
            winner = opponent_label
        else:
            winner = "DRAW"
        rows.append(
            {
                "battle_id": bid,
                "winner": winner,
                "turns": b.turn,
                "player_heuristic": player_label,
                "opponent_heuristic": opponent_label,
            }
        )
    return rows


async def main():
    # Total number of *battles* (each battle is v1 vs v2).
    TOTAL_GAMES = 10_000
    BATCH_SIZE = 500  # battles per outer loop (both directions combined)
    CONCURRENT_BATTLES = 20

    assert TOTAL_GAMES % BATCH_SIZE == 0, "TOTAL_GAMES must be multiple of BATCH_SIZE"
    assert BATCH_SIZE % 2 == 0, "BATCH_SIZE should be even (half per direction)"

    run_id = str(uuid.uuid4())[:4]
    data_dir = "data"
    csv_path = os.path.join(data_dir, f"tfm_doubles_v1_vs_v2_{run_id}.csv")
    os.makedirs(data_dir, exist_ok=True)

    config = ServerConfiguration("ws://127.0.0.1:8000/showdown/websocket", None)

    # One persistent instance of each heuristic; we just reset their battle logs between chunks.
    v1_player = TFMExpertDoublesV1(
        battle_format="gen9randomdoublesbattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"VGC_V1_{run_id}", None),
    )

    v2_player = TFMExpertDoublesV2(
        battle_format="gen9randomdoublesbattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"VGC_V2_{run_id}", None),
    )

    print(f"🚀 Iniciando Experimento v1 vs v2 (Doubles): {TOTAL_GAMES} partidas totales")
    print("  - Mitad con v1 como jugador y v2 como oponente")
    print("  - Mitad con v2 como jugador y v1 como oponente")

    with tqdm(total=TOTAL_GAMES, desc="Simulando Batallas v1 vs v2", unit="game") as pbar:
        batches = TOTAL_GAMES // BATCH_SIZE
        per_direction = BATCH_SIZE // 2

        for _ in range(batches):
            extracted_data = []

            # 1) v1 como "player", v2 como "opponent"
            await v1_player.battle_against(v2_player, n_battles=per_direction)
            extracted_data.extend(_extract_results(v1_player, "v1", "v2"))
            v1_player.reset_battles()
            v2_player.reset_battles()
            pbar.update(per_direction)

            # 2) v2 como "player", v1 como "opponent"
            await v2_player.battle_against(v1_player, n_battles=per_direction)
            extracted_data.extend(_extract_results(v2_player, "v2", "v1"))
            v1_player.reset_battles()
            v2_player.reset_battles()
            pbar.update(per_direction)

            if extracted_data:
                batch_df = pd.DataFrame(extracted_data)
                batch_df.to_csv(csv_path, mode="a", header=not os.path.exists(csv_path), index=False)


if __name__ == "__main__":
    asyncio.run(main())

