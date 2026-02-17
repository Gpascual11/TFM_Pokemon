### 1. Definició del Sistema (Game Theory Context)

* **Tipus de Joc:** Joc d'estratègia per torns de **Suma Zero** (Zero-Sum Game) amb **Informació Imperfecta** (Imperfect Information) i elements **Estocàstics**.
* **Comparativa:** Sovint descrit com "Escacs (estratègia posicional) + Pòquer (gestió de probabilitats i informació oculta)".
* **Espai d'Estats:** Combinatòria incommensurable ($> 10^{100}$ estats possibles considerant HP exacte, PP, RNG, etc.).
* **Observabilitat:** És un problema **POMDP** (Partially Observable Markov Decision Process). L'agent no coneix els 4 moviments, l'objecte, els EVs ni el Pokémon de reserva del rival fins que es revelen.

### 2. Format VGC (Video Game Championships)

*Si el teu TFM es basa en VGC, estàs treballant amb **Dobles**. Això augmenta la complexitat exponencialment respecte a "Singles" a causa de la selecció d'objectius (targeting).*

* **Regles Principals:**
* **Team Preview:** Es presenten equips de 6 Pokémon (Open Team Sheets o Closed, depenent del reglament vigent).
* **Selecció:** Es trien 4 Pokémon per al combat (Bring 6, Pick 4).
* **Nivell:** Tots els Pokémon s'ajusten a **Lv. 50**.
* **Restriccions:** Species Clause (no Pokémon repetits) i Item Clause (no objectes repetits).


* **Meta-game:** Conjunt limitat de Pokémon i estratègies òptimes que defineixen la distribució de probabilitats dels equips rivals.

### 3. Taula de Tipus i Càlcul de Dany

* **Matriu de Relacions:** 18 Tipus elementals.
* **Multiplicadors:**
* Immune ($0\times$)
* Not very effective ($0.5\times$)
* Neutral ($1.0\times$)
* Super Effective ($2.0\times$)


* **Dual Typing:** La majoria de Pokémon tenen 2 tipus. El multiplicador defensiu és el producte de tots dos.
* *Exemple:* Foc/Volador rep $2.0 \times 2.0 = 4.0\times$ de dany de Roca.


* **STAB (Same Type Attack Bonus):** Si el tipus de l'atac coincideix amb un dels tipus de l'atacant, el dany es multiplica per $1.5\times$ (o $2.0\times$ amb l'habilitat *Adaptability*).
* **La teva pregunta:** *"Aquí tenim en compte el tipus de l'atac contra el del pokemon no?"*
* **Resposta:** Sí. Sempre és: **Tipus del Moviment (Atacant)** vs. **Tipus del Pokémon (Defensor)**. El tipus del Pokémon atacant només serveix per al STAB, no per a l'eficàcia.



### 4. Estadístiques (Stats) i Matemàtiques

Cada Pokémon té 6 estadístiques base. El valor final a nivell 50 es calcula així:

#### Fórmula General (Excepte HP)
$$Stat = \left\lfloor \left( \frac{(2 \times Base + IV + \lfloor \frac{EV}{4} \rfloor ) \times Level}{100} + 5 \right) \times Nature \right\rfloor$$
#### Fórmula HP (Hit Points)
$$HP = \left\lfloor \frac{(2 \times Base + IV + \lfloor \frac{EV}{4} \rfloor ) \times Level}{100} \right\rfloor + Level + 10$$

*(Nota: Shedinja és l'excepció, sempre té 1 HP).*

* **Truncament:** El joc sempre arrodoneix cap avall ($\lfloor x \rfloor$) a cada pas de la multiplicació.
* **Divisió Físic/Especial:**
* **Physical:** Càlcul utilitza `Atk` vs `Def`. (Contacte físic generalment).
* **Special:** Càlcul utilitza `Sp.Atk` vs `Sp.Def`. (Projectils/màgia generalment).
* *Nota:* Abans de la Gen 4, això depenia del tipus. Ara depèn del moviment específic.



### 5. Velocitat i Prioritat (Speed Dynamics)

La velocitat determina l'ordre d'execució. És l'únic stat que no té "RNG" en el valor, és binari: o ets més ràpid o no.

1. **Speed Tiers:** Si $Speed_A > Speed_B$ A ataca primer.
2. **Speed Tie:** Si $Speed_A = Speed_B$, hi ha un 50% de probabilitat (coin flip) de qui ataca primer.
3. **Prioritat (Priority Bracket):** Supera la velocitat.
* Els moviments tenen un rang de prioritat de $+5$ (ex: *Helping Hand*) a $-7$ (ex: *Trick Room*).
* Un moviment amb prioritat $+1$ sempre va abans que un de $+0$, independentment de la velocitat (ex: *Aqua Jet* vs *Thunderbolt*).
* **Habilitat Prankster:** Dona prioritat $+1$ als moviments d'estat (Status moves).


4. **Dinàmica Gen 8+:** La velocitat es recalcula **immediatament** després de qualsevol acció (ex: si utilitzes *Tailwind*, la velocitat es dobla a l'instant per a la resta del torn).

### 6. Estats Alterats (Status Conditions)

Només un "Non-Volatile Status" alhora (es mostren al costat de la barra de vida).

* **Burn (Cremada):**
* Dany: 1/16 dels HP màxims al final del torn (Gen 7+).
* Efecte: **Redueix l'Attack (Físic) del Pokémon cremat en un 50%**.


* **Paralysis (Paràlisi):**
* Efecte: **Redueix la Speed en un 50%** (Gen 7+).
* Probabilitat: 25% de probabilitat de no moure's ("Full Para").


* **Poison (Verí):** 1/8 dels HP per torn.
* **Badly Poison (Toxic):**
* Dany acumulatiu: $1/16, 2/16, 3/16...$
* **La teva pregunta:** *"Can reset?"* -> **Resposta:** Sí. Si el Pokémon canvia (switch out), el comptador es reinicia a 1/16 quan torna a entrar.


* **Sleep (Son):**
* Durada: 1-3 torns.
* Mecànica: El comptador es pausa en canviar? Depèn de la generació, però a Showdown generalment es considera que la durada està prefixada al moment d'adormir-se.


* **Freeze (Congelació):**
* 20% de probabilitat de descongelar-se cada torn.



### 7. Spread Damage (Dany en Àrea - Dobles)

Mecànica crítica per al VGC.

* **Regla del 75%:** Els moviments que impacten a **tots** els rivals (ex: *Eruption, Rock Slide*) o a **tots** els Pokémon (ex: *Earthquake*) veuen el seu dany reduït al 75% per objectiu.
* **La teva pregunta:** *"Except if the other pkm is knocked out?"*
* **Resposta:** NO (amb matisos). Si selecciones un moviment Spread (com *Rock Slide*) i només encertes a un rival (perquè l'altre ha fallat o utilitza *Protect*), el dany **continua sent del 75%**.
* *Excepció:* Si només queda un rival al camp des de l'inici del torn, llavors alguns jocs ho tracten com a single target, però per seguretat assumeix sempre la penalització de spread en dobles si el moviment és d'àrea.



### 8. Variables Ocultes (IVs i EVs) - El repte de la IA

Aquí és on entra la teva part de Data Science (Inferència).

* **IVs (Individual Values):** Genètica (0-31). En VGC s'assumeix 31 en tot (o 0 en Velocitat per a equips de *Trick Room*, o 0 en Atac per reduir dany de *Confusion/Foul Play*).
* **EVs (Effort Values):** Entrenament (0-252).
* Total màxim: 508. Màxim per stat: 252.
* **Matemàtica a Nivell 50:**
* Els primers 4 EVs donen +1 punt d'estadística.
* Després, calen 8 EVs per cada +1 punt addicional.
* Fórmula simplificada: $Punts = \lfloor (EVs - 4) / 8 \rfloor + 1$.
* *Implicació:* Les distribucions òptimes sempre són $4 + 8n$ (ex: 4, 12, 20... 252).


### 9. Elements de Camp (Field Effects)

Són variables globals que afecten el vector d'estat de la IA.

* **Weather (Clima):** Sun, Rain, Sand, Snow. (Duren 5 torns).
* **Terrains (Terrenys):** Electric, Grassy, Misty, Psychic. (Augmenten dany un 30% en Gen 8+, abans 50%).
* **Speed Control:** *Tailwind* (dobla velocitat 4 torns), *Trick Room* (inverteix l'ordre de velocitat 5 torns).
