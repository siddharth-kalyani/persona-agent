# 08e: Hardware engineering and partner options (fact sheet)

Raw input for `08-ai-hardware-lessons.md`, Section D. Compiled 2026-10-06.

**Confidence labels.**
- **High**: read on the primary source this session.
- **Med**: a vendor claim or an inference from the docs.
- **Unverified (memory)**: analyst recall, not re-checked. WebSearch was exhausted, so only WebFetch was possible.
- **EST**: an analyst estimate.

**Constraints applied:** per-seat M365 buyers, US and India first, 3–6 engineers, a 3-month phone-first MVP, and a work-only recorder governed by the tenant.

## 1. Chips used by existing devices

| Device | Claim | Source | Conf. |
|---|---|---|---|
| Omi pendant | The board files target the nRF5340 (`omi_nrf5340_cpuapp`, `..._cpunet`). They also include nRF70 Wi-Fi files (`nrf70_common.dtsi`). | https://github.com/BasedHardware/omi/tree/main/omi/firmware/boards/omi | High for nRF5340. Med that the Wi-Fi chip is fitted. |
| Omi DevKit 2 | Built on the Seeed XIAO BLE Sense (`xiao_ble_sense_devkitv2-adafruit`; nRF52840) | https://github.com/BasedHardware/omi/tree/main/omi/firmware | High for the board. The MCU is unverified (memory). |
| Omi firmware | Zephyr with the nRF Connect SDK; stores Opus-encoded audio; documents OTA (`BUILD_AND_OTA_FLASH.md`) | same | High |
| Omi Glass | ESP32-S3, with camera and audio | https://github.com/BasedHardware/omi | High |
| Plaud, Limitless, Bee, Friend, Sandbar, Index 01 | SoC not published | n/a | Not verified |
| Humane AI Pin, Rabbit R1 | Phone-class SoCs: a Snapdragon in the Pin; a Helio P35 with 4 GB RAM and 1,000 mAh in the R1 | Humane/Rabbit fact sheets | Unverified (memory) |

**Pattern (Med).** Both failed devices ran full operating systems on phone-class processors, with the heat, idle drain and cloud round-trips that implies. The recorders that last a day or more (Omi, Plaud) use microcontrollers that encode, buffer and hand off to the phone.

## 2. Candidate SoCs

| SoC | Compute and memory | Radio | Security | Fit | Conf. |
|---|---|---|---|---|---|
| [nRF5340](https://www.nordicsemi.com/Products/nRF5340) | Application core: M33 at 128/64 MHz, 1 MB flash, 512 KB RAM. Network core: M33 at 64 MHz, 256 KB flash, 64 KB RAM. | BLE with LE Audio (the page cites Bluetooth 5.4) | TrustZone, CryptoCell-312, key management unit; **PSA Certified Level 2** | **Default choice.** Proven in Omi. aQFN94 7×7 mm or WLCSP 4.4×4.0 mm. | High |
| [nRF54L15](https://www.nordicsemi.com/Products/nRF54L15) | M33 at 128 MHz; 1.5 MB NVM, 256 KB RAM; 193 CoreMark/mA | RX 3.4 mA, TX 4.8 mA at 0 dBm, 3 V; sleep 0.7–2.9 µA | TrustZone, tamper detection, crypto engine with side-channel protection | Cost-down v2 (CSP 2.45×2.25 mm). The page does not mention LE Audio. Check that Opus fits in 256 KB RAM. | High |
| [nRF54H20](https://www.nordicsemi.com/Products/nRF54H20) | Several M33 cores up to 320 MHz plus RISC-V; 2 MB NVM, 1 MB RAM | Bluetooth 6.0 features; RX from 1.7 mA; up to +10 dBm | Designed for **PSA Certified Level 3**; tamper sensors | Only if on-device ML is needed | High |
| [ESP32-S3](https://www.espressif.com/en/products/socs/esp32-s3) | Dual LX7 at 240 MHz; 512 KB SRAM; PSRAM | Wi-Fi 4 plus BLE 5. No Classic Bluetooth or LE Audio listed. | Secure boot, AES-XTS flash encryption, digital signature, HMAC, World Controller | Suits camera devices. Too power-hungry for a 24 h pendant (power claim unverified (memory)). | High for specs |
| [Apollo510/510B](https://ambiq.com/apollo510/) | M55 with Helium at 250 MHz; up to 4 MB NVM, 3.75 MB SRAM | BLE 5.4, on the 510B only | secureSPOT, TrustZone, PUF, tamper-resistant OTP | Ultra-low-power always-on voice (2 PDM inputs, always-on audio ADC). Small ecosystem; power figures not published. | High for specs |

**Indicative chip prices (EST, unverified (memory)).**

| Chip | Indicative price (US$) |
|---|---|
| nRF52840 | 2.5–4 |
| nRF5340 | 3.5–6 |
| nRF54L15 | 1.5–3 |
| ESP32-S3 | 2–3 for the chip |

Get distributor quotes at 1k and 10k units.

## 3. Microphones

| Claim | Source | Conf. |
|---|---|---|
| The TDK T5838 PDM mic has Acoustic Activity Detect (wake-on-sound) at "as low as 20 µA". SNR 68 dB; AOP 133 dB SPL; −41 dBFS; 3.50×2.65×0.98 mm. TDK claims 50–70% lower power than competitors. | https://invensense.tdk.com/products/digital/t5838/ | High |
| Infineon IM69D130/IM73D122 and Knowles SPH0641 mics are alternatives (SNR about 69–73 dB; about 0.5–1 mA in normal mode) | n/a | Unverified (memory) |
| The Plaud Note Pro uses a 4-mic array | https://dev.plaud.ai/ | High |

**Design note (judgement).** Two mics 10–20 mm apart give noise reduction and help tell the wearer from other speakers. Meeting capture needs every speaker, so beamforming should improve clarity, not exclude others. That puts more weight on consent and notice design (legal track).

## 4. Codec, BLE transport and phone background rules

| Claim | Source | Conf. |
|---|---|---|
| Opus covers wideband speech from 10 kb/s and fullband from 16 kb/s mono; "24 Kb/s should give fullband". Default frame is 20 ms; complexity 0–10 trades quality for CPU. | https://wiki.xiph.org/Opus_Recommended_Settings | High |
| Opus runs on a Cortex-M33 in a shipping product: Omi encodes on the nRF5340 ("full BLE + Opus + Deepgram"). | Omi GitHub | High |
| Data volume: PCM at 16 kHz/16-bit is 115 MB/h. Opus is 10.8 MB/h at 24 kb/s and 7.2 MB/h at 16 kb/s. A 128 MB buffer holds about 11.9 h at 24 kb/s or about 17.8 h at 16 kb/s. | arithmetic | EST |
| BLE GATT throughput (2M PHY plus data-length extension) reaches hundreds of kb/s, so a backlog syncs at 10× real time or faster | n/a | Unverified (memory) |
| A custom GATT service carrying Opus works on both iOS and Android. LE Audio/LC3 is optional. | judgement | Med |

**iOS (Apple [Core Bluetooth background guide](https://developer.apple.com/library/archive/documentation/NetworkingInternetWeb/Conceptual/CoreBluetooth_concepts/CoreBluetoothBackgroundProcessingForIOSApps/PerformingTasksWhileYourAppIsInTheBackground.html); High).**
- With the `bluetooth-central` mode, the system wakes the app when "a peripheral sends updated characteristic values".
- Each wake gives the app "around 10 seconds". Heavy background use can get the app "throttled back… or killed".
- Background scanning is slower.
- State restoration "relaunches your app into the background" after the system has terminated it.
- Apple asks that such apps be "session based", with user start/stop.
- That a force-quit blocks relaunch is unverified (memory).

**Android (developer.android.com; High).**
- On Android 12+, an app cannot start a foreground service from the background. One exemption is a Companion Device Manager (CDM) association plus `REQUEST_COMPANION_START_FOREGROUND_SERVICES_FROM_BACKGROUND` or `REQUEST_COMPANION_RUN_IN_BACKGROUND` ([restrictions](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start)).
- On Android 14+, a `microphone` foreground service cannot be created from the background (it throws `SecurityException`).
- A `connectedDevice` service needs `FOREGROUND_SERVICE_CONNECTED_DEVICE` plus, for example, `BLUETOOTH_CONNECT`. It does **not** need `RECORD_AUDIO` ([types](https://developer.android.com/develop/background-work/services/fgs/service-types)).
- On Android 16, `startObservingDevicePresence(ObservingDevicePresenceRequest)` binds the app's `CompanionDeviceService` while the device is in range. CDM scanning needs no fine-location permission, but Location Services must be on ([CDM](https://developer.android.com/develop/connectivity/bluetooth/companion-device-pairing)).

**Implication (Med–High; a prototype must prove it).** A dedicated BLE recorder sidesteps the rule that an app cannot start the phone mic from the background, because the audio arrives as Bluetooth data.
- **Android:** the CDM association plus a `connectedDevice` service lets the app restart from the background.
- **iOS:** BLE wake-ups do not guarantee continuous runtime. Firmware must therefore **store and forward**: buffer on the device and let the phone drain it on each wake.
- Android OEM battery killers (Xiaomi, Oppo, Vivo, Samsung; common in India) still need a test matrix (unverified (memory)).

## 5. Battery benchmarks and power budget

| Device | Claim | Source | Conf. |
|---|---|---|---|
| Plaud NotePin | 20 h recording, 40 days standby; 64 GB; 16.6 g; $159 | https://www.plaud.ai/products/notepin | High (vendor) |
| Plaud NotePin S / Note Pro | 20 h / 30–50 h | https://dev.plaud.ai/ | High |
| Omi | "24h+ continuous capture" | Omi README | Med |
| Index 01 ring | Non-rechargeable silver-oxide: about 12–15 h of recording in total, "up to 2 years". Records only while the button is pressed. $75/$99; ships March 2026. | https://repebble.com/index | High |
| Limitless / Bee | About 100 h / about 7 days | n/a | Unverified (memory) |

**Power budget (EST, nRF5340-class, continuous capture).**

| Block | Average current (EST) |
|---|---|
| 2 mics, normal mode | about 1.0 mA |
| MCU: capture, DSP, Opus | 2.5–3.5 mA |
| BLE batched notifications | 0.5–1.0 mA |
| Flash writes | 0.2–0.4 mA |
| PMIC quiescent, LED at about 10% duty, misc. | 0.3–0.5 mA |
| **Total** | **4.5–6.4 mA; plan on 5.5 mA** |

**Battery sizing (EST).** Required capacity = hours × mA ÷ 0.8 (derating).

| Scenario | Calculation | Capacity |
|---|---|---|
| 24 h always-on | 24 × 5.5 ÷ 0.8 | **about 165 mAh** |
| 48 h always-on | 48 × 5.5 ÷ 0.8 | **about 330 mAh** |
| Wake-on-sound, 24 h | AAD at 20 µA, MCU idle in silence, speech 35% of the time: 0.35 × 5.5 + 0.65 × 0.3 ≈ **2.1 mA** | about 63 mAh |
| Wake-on-sound, 5 × 10 h workdays | (105 + 3.5 standby) ÷ 0.8 | **about 136 mAh** |

**Target (judgement):** at least 24 h of capture from a 150–250 mAh cell, and a full week with wake-on-sound.

## 6. Indicative BOM for a BLE badge at 10k units (EST)

No teardown BOM could be verified for Humane, Rabbit, Plaud or Omi. All figures are memory-based estimates; replace them with real quotes.

| Item | EST US$ |
|---|---|
| nRF5340, crystals, RF matching, antenna | 4.5–7.0 |
| 2 MEMS mics | 0.6–1.5 |
| 128 MB SPI flash | 1.0–2.5 |
| PMIC, charger, fuel gauge (nPM1300 class) | 1.0–2.0 |
| 150–250 mAh LiPo, UN38.3 | 1.0–2.5 |
| Optional secure element | 0.6–2.0 |
| Mute slide switch, button, LED with light pipe, haptic | 0.6–1.5 |
| PCB, assembly, test | 2.0–4.0 |
| Enclosure, clip, lanyard | 1.5–5.0 |
| Cradle or pogo pins, cable | 1.0–3.0 |
| Packaging | 1.0–2.5 |
| **Ex-factory** | **about 15–33** |
| **Landed** (freight, duty, yield, warranty: +20–40%) | **about 18–46** |

**Retail anchors:** Plaud NotePin $159 and Index 01 $75–99 (High). Omi about $89, Bee $49.99, Limitless $99 (unverified (memory)).

**One-time costs (EST).**

| Item | EST |
|---|---|
| Industrial and mechanical design | $20–100k |
| Tooling | $10–60k |
| Certification (US, EU, UK, India) | $15–60k |
| Electrical and firmware engineering | 2 engineers for 6–9 months |

## 7. Manufacturing

**Timeline (EST).**

| Phase | Units | Duration |
|---|---|---|
| Proof of concept (dev kits, Omi or Plaud devices) | 5–20 | 0–2 months |
| Works-like / looks-like prototypes | 20–50 | 2–4 months |
| EVT | 50–200 | 2–3 months |
| DVT (hard tooling, certification, reliability) | 200–1,000 | 2–4 months |
| PVT | 500–2,000 | 1–2 months |
| **Prototype to mass production** | n/a | **about 9–15 months** |

**MOQ (EST).**
- **Custom-tooled builds:** 1k–5k units per run.
- **White-label ODM recorders:** MOQ 500–3,000. Shenzhen and Alibaba suppliers exist; none verified.
- **Small-run EMS:** 100–1,000 boards.

**India options (all unverified (memory); verify before outreach).**

| Option | Notes |
|---|---|
| Dixon Technologies (Noida) | Largest Indian-owned EMS. Reportedly builds wearables and hearables for Indian brands. |
| Optiemus Electronics (Noida) | Phones, wearables, hearables. Reportedly a partner to brands such as Noise and boAt. |
| VVDN Technologies (Gurugram/Manesar) | Design-and-manufacture ODM. Best fit at low volume. |
| Kaynes Technology (Mysuru) | EMS/ODM for IoT and industrial |
| Syrma SGS (Chennai) | EMS, RFID, IoT |
| Tata Electronics (Hosur) | Apple-scale; not a small-run option |

- **Incentives (unverified (memory)):**
  - The PLI schemes cover smartphones and IT hardware, not wearables.
  - SPECS gave a 25% capex incentive to component makers and is closed.
  - The 2025 component scheme (about ₹22,919 crore) targets components.
  - Any benefit reaches us indirectly, through EMS partners.
- **Duties (unverified (memory)):** India's duty on finished wearables is high (about 20%), which favours local assembly. Confirm the tariff line with a broker.

**US options (unverified (memory)).** Jabil, Flex and Sanmina want large programmes. Below 10k units, use small-run providers (MacroFab, Screaming Circuits, Sierra Circuits) or a regional mid-tier EMS. US tariffs changed repeatedly in 2025, so model several scenarios.

**Enterprise supply checklist (judgement).**
- Serial numbers bound to keys at the factory.
- Signing keys held in an HSM.
- Country-of-origin documents.
- A replacement pool covering 2–3 years.
- Second sources for the mics, flash and battery.

## 8. Security implementation

| Control | Implementation | Conf. |
|---|---|---|
| Root of trust | nRF5340: key management unit with CryptoCell (PSA L2). nRF54H20: designed for PSA L3. Apollo510: PUF. ESP32-S3: secure boot and flash encryption. (vendor pages) | High |
| Secure boot and OTA | nRF Connect SDK: an immutable bootloader plus MCUboot with signed images and anti-rollback; DFU over BLE via MCUmgr/SMP. Omi documents an OTA flow. | Med (memory) |
| Identity and attestation | A per-device key pair created at the factory, a certificate from our device CA, and a PSA attestation token via TF-M | Med (memory) |
| Encrypted buffer | AES on each audio chunk. Session keys are wrapped to a cloud key, so the device and phone cannot decrypt stored history. Unbinding crypto-erases the data. Precedent: Plaud binds each device to one app "so even if a device is stolen, the data remains inaccessible". | High (precedent) |
| Pairing | LE Secure Connections with out-of-band QR/NFC pairing, never "Just Works", plus app-layer end-to-end encryption | Med |
| Secrets | No third-party keys on the device or in the app; the backend mints short-lived tokens (the lesson from Rabbit's hard-coded keys) | High (principle) |
| EU | RED delegated act / EN 18031. Plaud already claims EN 18031. | High (Plaud claim) |

## 9. Enterprise fleet: provisioning and MDM

| Claim | Source | Conf. |
|---|---|---|
| Intune app configuration sends developer-defined key-value settings through two channels. **Managed devices** use the MDM channel. **Managed apps** use the Intune App SDK and need no device enrollment. | https://learn.microsoft.com/en-us/intune/intune-service/apps/app-configuration-policies-overview | High |
| Managed apps check in every 30 min when an app protection policy is assigned, otherwise every 720 min. The managed-apps channel requires Android 10+. Config is also available through Graph. | same | High |
| Intune does not manage BLE accessories. The badge is managed through our app and cloud. | inference | Med |

**Provisioning flow (our design).**
1. Inject keys at the factory and register each device's serial number and public key.
2. The admin assigns devices to users.
3. The user signs into the companion app with Entra ID.
4. The device pairs out-of-band via QR or NFC.
5. The device is bound to one tenant.
6. Signed policies (allowed hours and locations, mute default, retention, redaction) go out through Intune app config and our admin API.
7. The firmware enforces the policy.
8. To offboard: revoke the certificate and crypto-erase the device.

**Form factor:** a badge on a lanyard or a magnetic clip, with a recording LED and a mute switch.

## 10. Partner options and HaaS precedents

| Option | Facts | Feasibility | Conf. |
|---|---|---|---|
| **Plaud Embedded** | **SDK:** iOS 14+ and Android 5.0+; "BLE device pairing out-of-the-box"; start and stop recordings from your app. **Data path:** audio syncs to your backend over BLE or Wi-Fi; you pass a `file_url` to Plaud for transcription (112 languages). **Binding:** each device binds to **one app**. **Free tier:** 300 hours and 50 devices. **Devices:** Note Pro and NotePin S. **Licence and compliance:** Apache-2.0 Swift SDK; SOC 2, HIPAA, ISO 27001, EN 18031. ([dev.plaud.ai](https://dev.plaud.ai/), [docs](https://docs.plaud.ai/plaud-embedded/overview), [GitHub](https://github.com/Plaud-AI)) | **Best near-term pilot path.** Still to verify: whether raw audio can skip Plaud's cloud, data residency in the US and India, pricing, and fleet controls. | High for the docs |
| **Omi** | MIT licence; open hardware; nRF5340; BLE protocol SDKs in many languages | Fine for internal pilots, or as a reference design for our own badge | High; Low for enterprise readiness |
| Limitless, Bee | Closed after their acquisitions | Not viable | Med |
| Earbuds | AirPods recording API on iOS 26 (unverified (memory)); phone-mic rules still apply | Not an always-on room recorder | Med |
| Meta glasses toolkit | Covered by another track | n/a | n/a |

**HaaS precedents (unverified (memory)).**
- Plaud: device plus minute tiers.
- Humane: $699 plus $24/mo.
- Samsara: devices bundled into subscription licences.
- Vocera/Stryker: badges plus licences.
- Theatro: subscription.
- HP DaaS, Dell APEX, Lenovo TruScale: monthly per-device fees.

**Pricing (EST).** A landed cost of $25–50 over 24 months comes to about $1–2 a month. Add a replacement pool and logistics, and an add-on of about $5–10 per user per month covers it. Alternatively, include a device with annual commitments above a seat threshold.

## 11. Uncertainties and unverified items

1. SoCs for most recorders.
2. All prices and BOM figures (EST).
3. Mic currents for the Infineon and Knowles parts.
4. Real-world BLE throughput, iOS force-quit behaviour, and Android OEM app killers.
5. The Plaud Embedded audio path, data residency and pricing.
6. India EMS and scheme details, duty rates, and US tariffs.
7. Battery claims for Limitless, Bee, Friend and Sandbar.
8. HaaS price points.
9. AirPods API details.
