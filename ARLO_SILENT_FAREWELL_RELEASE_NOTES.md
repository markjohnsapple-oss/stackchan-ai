# ARLO Silent Goodbye v2 | Firmware Release Notes

## Base preserved
Build is based on the successful ARLO Slim v1 hands-free and naming firmware. It keeps the original Slim v1 manufacturer bootloader, partitions, generated artwork, OTA metadata and flash manifests unchanged and hash-verified. All saved settings, Wi-Fi pairing, user personality and NVS remain untouched.

## One correction
The first silent-goodbye experiment was unsuccessful on the user's physical ARLO because it tried to identify a server-generated TTS farewell after it started. The experimental filter has now been replaced, not stacked.

The updated implementation uses the existing XiaoZhi voice channel and its VAD. After 18 seconds of *genuine inactivity* while in listening mode and with playback drained, ARLO closes the idle cloud audio channel **before** the hosted server's roughly 30-second goodbye could arrive. His existing hands-free logic automatically opens another session. Actual voice input, normal AI speech and camera/motor behaviour remain enabled. This can introduce a brief connection pause during idle transitions.

## Scope
No changes to the cloud service address, OTA, identity, Wi-Fi, camera, servos, speech decoder, TTS, or user settings. No added server, Bluetooth or background task. On-device name ARLO and wake-free conversation remain.

## Test
GitHub checks compile and binary integrity; the new idle behavior and sound must still be confirmed on ARLO's physical hardware. Test (1) an ordinary voice conversation, (2) at least 60 seconds of silence, (3) responsiveness when speaking again. If there is a reconnect pause or farewell speech persists, preserve the results for further investigation rather than assuming success.

## Flashing
Same five binaries, addresses and 80 MHz / DIO / 16 MB settings as the installed ARLO package. Do not erase NVS. Keep the previously working package for rollback.
