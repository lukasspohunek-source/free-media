# Bezplatné backendy

Stav primárních zdrojů zkontrolován 20. 10. 2026. Adresy, licence, runtime a schémata se mohou změnit; před každou generací použít aktuální kontrolu CLI. Záznam níže nepotvrzuje, že byla konkrétní generace dokončena.

## Povolená veřejná Spaces

| CLI backend | Oficiální Space | Endpoint | Úsporné nastavení |
| --- | --- | --- | --- |
| `image` | [black-forest-labs/FLUX.2-klein-4B](https://huggingface.co/spaces/black-forest-labs/FLUX.2-klein-4B) | `/infer` | `Distilled (4 steps)`, 4 kroky, guidance 1, enhancer vypnutý, pevný seed |
| `video` | [Lightricks/LTX-2.5](https://huggingface.co/spaces/Lightricks/LTX-2.5) | `/run` | 2 sekundy, 896 × 512, `conv`, auto length i enhancer vypnuté, pevný seed |

Použít jen anonymního klienta bez uživatelského tokenu. Nekopírovat tokeny ze serverového zdrojového kódu, nečíst lokální přihlašovací cache a nevolat položku „Inference Providers“ na stránce modelu; ta představuje jinou službu než uvedené Space.

## Schéma pro kontrolu implementace

Pořadí níže je odečtené ze zdrojového kódu, není náhradou za aktuální Gradio schema. Při neshodě nic neodesílat a ověřit změnu. Soubor nahrát přes podporovaný mechanismus klienta; lokální cestu neposílat jako předpokládanou cestu na vzdáleném serveru.

### Obrázek: FLUX.2-klein-4B

Zdroj: [app.py oficiálního Space](https://huggingface.co/spaces/black-forest-labs/FLUX.2-klein-4B/blob/main/app.py).

```text
/infer(
  prompt,
  input_images,
  mode_choice,
  seed,
  randomize_seed,
  width,
  height,
  num_inference_steps,
  guidance_scale,
  prompt_upsampling
)
→ image, used_seed
```

Použít `mode_choice="Distilled (4 steps)"`, `randomize_seed=False`, `num_inference_steps=4`, `guidance_scale=1.0`, `prompt_upsampling=False`. Parametr `input_images` je galerie; jedinou referenci namapovat na její aktuální datové schéma, ne na samostatný textový řetězec. Serverový enhancer jinak používá další inference službu.

### Video: LTX-2.5

Zdroj: [app.py oficiálního Space](https://huggingface.co/spaces/Lightricks/LTX-2.5/blob/main/app.py).

```text
/run(
  prompt,
  image_path,
  height,
  width,
  duration_s,
  seed,
  decoder,
  auto_len,
  randomize_seed,
  do_enhance
)
→ video, used_prompt, used_seed, length_text
```

Pozor na pořadí: výška před šířkou. Použít `decoder="conv"`, `auto_len=False`, `randomize_seed=False`, `do_enhance=False`. Šířka i výška musí být dělitelné 64. Referencí se podmiňuje první snímek. Nevolat automaticky samostatný enhancer ani endpoint příkladů; mohly by spotřebovat další kvótu.

## Runtime, kvóta a opakování

[Oficiální pravidla ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu) při kontrole uváděla 2 minuty denně bez přihlášení a 5 minut pro bezplatný účet. `xlarge` používá 96GB Blackwell GPU a kvótu čerpá dvojnásobně; LTX-2.5 jej používá. Tyto hodnoty uvádět s datem, nepovažovat je za trvalé ani za záruku volné kapacity.

Vyžadovat živé potvrzení runtime typu ZeroGPU, schválené revize a očekávaného endpointu před odesláním promptu nebo reference. Nevyvozovat skutečné běžící GPU pouze z názvu Space, loga „free“ nebo archivovaného README. Při nedostupném metadatovém ověření skončit bez generace.

Jedno volání `generate` smí založit nejvýše jeden požadavek. Při ztrátě spojení po odeslání uvést nejistý stav; neprovádět automatický retry ani přepnutí na druhý backend. Respektovat limit služby, nepoužívat další identity k obcházení kvóty. Anonymní režim nedovoluje čerpat uživatelské platební kredity; na přihlášený účet se v této verzi nepřepínat.

## Licence kódu a vah

Posuzovat odděleně zdrojový kód aplikace, konkrétní modelové váhy a podmínky hostované služby. Odkaz na GitHub sám nepotvrzuje bezplatné používání modelu.

- **FLUX.2-klein-4B:** [modelová karta](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) označuje konkrétní 4B váhy jako Apache 2.0. Nezobecňovat to na 9B či jiné modely FLUX. Zdroj hostované implementace je odkazován výše; při přebírání jeho kódu zkontrolovat licenci dané revize zvlášť.
- **LTX-2.5:** [oficiální repo](https://github.com/Lightricks/LTX-2) odkazuje na [LTX-2.x Community License](https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x). Ta stanoví podmínky bezpoplatkového použití a placenou licenci od ročních příjmů entity 10 milionů USD s vymezenými nekomerčními výjimkami. Nepopisovat LTX-2.5 jako Apache/MIT ani jako neomezeně použitelný model. Pro místní stažení vah může být vyžadováno přijetí podmínek; veřejné demo a stažení vah jsou odlišné cesty.

## Lokální GPU: jen podklady pro budoucí rozšíření

Lokální inference není v tomto CLI implementována. Nestahovat váhy ani neinstalovat prostředí automaticky při selhání veřejného Space.

| Možnost | Doložený výchozí profil | Primární zdroj |
| --- | --- | --- |
| FLUX.2-klein-4B | Výrobce uvádí přibližně 13 GB VRAM; skutečný profil závisí na offloadu a velikosti obrazu. | [Model](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) |
| LTX Desktop | 24 GB+ VRAM, 32 GB RAM a 100 GB+ volného disku; místní textový enkodér umožňuje provoz bez API klíče. | [Oficiální požadavky](https://github.com/Lightricks/LTX-Desktop/blob/main/docs/setup-and-settings.md) |
| Wan2.2-TI2V-5B | Oficiální příklad s offloadem a CPU textovým enkodérem uvádí 24 GB VRAM; váhy Apache 2.0. | [Repo](https://github.com/Wan-Video/Wan2.2), [váhy](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B) |

Vlastní hardware odstraňuje poplatek za inference API, nikoli spotřebu elektřiny nebo čas výpočtu. U konkrétního stroje nejprve ověřit GPU, volnou VRAM, RAM a disk; dostupnost knihovny nebo repozitáře nevydávat za funkční lokální backend.
