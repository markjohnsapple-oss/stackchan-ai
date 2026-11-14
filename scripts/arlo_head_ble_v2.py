#!/usr/bin/env python3
"""Add direct BLE head control to pinned verified Slim v2 after ARLO silence guard.
Keeps original AI, microphone, camera, menu, servo limits and memory tuning.
Does not add a Wi-Fi or HTTP controller. Four-digit code is app-level, not OS pairing.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "upstream/firmware/main"
HAL = MAIN / "hal"

CPP = r'''// ARLO direct Bluetooth head joystick, independent of Wi-Fi and cloud.
// Exclusive AI mode add-on: preserves native StackChan UI, camera and voice.
#include "hal.h"
#include <stackchan/stackchan.h>
#include <host/ble_hs.h>
#include <host/ble_gap.h>
#include <host/ble_hs_id.h>
#include <host/util/util.h>
#include <host/ble_uuid.h>
#include <services/gap/ble_svc_gap.h>
#include <services/gatt/ble_svc_gatt.h>
#include <nimble/nimble_port.h>
#include <nimble/nimble_port_freertos.h>
#include <os/os_mbuf.h>
#include <esp_log.h>
#include <cstring>
#include <cstdint>

namespace {
static const char *TAG = "ARLO_BLE";
static const ble_uuid128_t kService = BLE_UUID128_INIT(
    0x01,0xa1,0x02,0x43,0x94,0xb9,0xfd,0x8d,0xeb,0x4e,0x21,0x8d,0xce,0xa9,0x96,0x1d);
static const ble_uuid128_t kControl = BLE_UUID128_INIT(
    0x02,0xa1,0x02,0x43,0x94,0xb9,0xfd,0x8d,0xeb,0x4e,0x21,0x8d,0xce,0xa9,0x96,0x1d);
static uint8_t own_address_type = 0;
static bool started = false;

// Fixed 8-byte command, safe at the minimum BLE ATT payload size:
// [0] magic A6, [1..4] code ASCII "0000", [5] 0=verify,1=move,2=stop,
// [6] signed yaw degrees, [7] pitch degrees.
static int on_control_write(uint16_t conn_handle, uint16_t attr_handle,
                            ble_gatt_access_ctxt *ctxt, void *arg) {
    (void)conn_handle; (void)attr_handle; (void)arg;
    if (ctxt->op != BLE_GATT_ACCESS_OP_WRITE_CHR || !ctxt->om ||
        OS_MBUF_PKTLEN(ctxt->om) != 8)
        return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
    uint8_t data[8] = {};
    if (os_mbuf_copydata(ctxt->om, 0, 8, data) != 0)
        return BLE_ATT_ERR_UNLIKELY;
    if (data[0] != 0xA6 || std::memcmp(data + 1, "0000", 4) != 0)
        return BLE_ATT_ERR_WRITE_NOT_PERMITTED;
    const uint8_t command = data[5];
    const int yaw = static_cast<int8_t>(data[6]);
    const int pitch = data[7];
    if (command == 0) return 0; // Verify controller and access code.
    if (command == 2) {
        LvglLockGuard lock;
        GetStackChan().motion().stop();
        return 0;
    }
    if (command != 1 || yaw < -25 || yaw > 25 || pitch < 5 || pitch > 30)
        return BLE_ATT_ERR_VALUE_NOT_ALLOWED;
    {
        LvglLockGuard lock;
        GetStackChan().motion().moveWithSpeed(yaw * 10, pitch * 10, 150);
    }
    return 0;
}
static const ble_gatt_chr_def chars[] = {
    { .uuid = &kControl.u, .access_cb = on_control_write, .flags = BLE_GATT_CHR_F_WRITE },
    { 0 }
};
static const ble_gatt_svc_def services[] = {
    { .type = BLE_GATT_SVC_TYPE_PRIMARY, .uuid = &kService.u, .characteristics = chars },
    { 0 }
};

static void advertise();
static int gap_event(ble_gap_event *event, void *arg) {
    (void)arg;
    switch (event->type) {
        case BLE_GAP_EVENT_CONNECT:
            if (event->connect.status != 0) advertise();
            break;
        case BLE_GAP_EVENT_DISCONNECT:
            // Do not leave a servo movement in progress after disconnect.
            {
                LvglLockGuard lock;
                GetStackChan().motion().stop();
            }
            advertise();
            break;
        case BLE_GAP_EVENT_ADV_COMPLETE:
            advertise();
            break;
        default: break;
    }
    return 0;
}
static void advertise() {
    ble_hs_adv_fields fields = {};
    const char name[] = "ARLO Head";
    fields.flags = BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP;
    fields.name = reinterpret_cast<const uint8_t*>(name);
    fields.name_len = sizeof(name) - 1;
    fields.name_is_complete = 1;
    int rc = ble_gap_adv_set_fields(&fields);
    if (rc != 0) {
        ESP_LOGW(TAG, "Set advertisement failed %d", rc);
        return;
    }
    ble_gap_adv_params params = {};
    params.conn_mode = BLE_GAP_CONN_MODE_UND;
    params.disc_mode = BLE_GAP_DISC_MODE_GEN;
    rc = ble_gap_adv_start(own_address_type, nullptr, BLE_HS_FOREVER,
                           &params, gap_event, nullptr);
    if (rc != 0) ESP_LOGW(TAG, "BLE advertisement failed %d", rc);
}
static void on_sync() {
    int rc = ble_hs_util_ensure_addr(0);
    if (rc == 0) rc = ble_hs_id_infer_auto(0, &own_address_type);
    if (rc != 0) {
        ESP_LOGE(TAG, "BLE address failed %d", rc);
        return;
    }
    ESP_LOGI(TAG, "ARLO Head discoverable by Bluetooth");
    advertise();
}
static void host_task(void *) {
    nimble_port_run();
    nimble_port_freertos_deinit();
}
} // namespace

void arlo_head_ble_start() {
    if (started) return;
    const esp_err_t err = nimble_port_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NimBLE start failed: %s", esp_err_to_name(err));
        return;
    }
    ble_hs_cfg.sync_cb = on_sync;
    ble_svc_gap_init();
    ble_svc_gatt_init();
    ble_svc_gap_device_name_set("ARLO Head");
    if (ble_gatts_count_cfg(services) != 0 || ble_gatts_add_svcs(services) != 0) {
        ESP_LOGE(TAG, "Failed to create ARLO Bluetooth service");
        return;
    }
    started = true;
    ESP_LOGI(TAG, "ARLO Bluetooth joystick ready. App code: 0000");
    nimble_port_freertos_init(host_task);
}
'''

def once(source, old, new, label):
    matches = source.count(old)
    if matches != 1:
        raise RuntimeError(f"STOP: unexpected {label}: {matches} matches")
    return source.replace(old, new, 1)

def patch():
    file = HAL / "hal.cpp"
    source = file.read_text(encoding="utf-8")
    source = once(source, "void Hal::startXiaozhi()\n{",
                  "void arlo_head_ble_start();\n\nvoid Hal::startXiaozhi()\n{", "AI startup")
    source = once(source, "    hal_bridge::start_xiaozhi_app();",
                  "    // Dedicated BLE controller starts without changing native XiaoZhi.\n"
                  "    arlo_head_ble_start();\n    hal_bridge::start_xiaozhi_app();",
                  "AI launch hook")
    file.write_text(source, encoding="utf-8")
    (HAL / "arlo_head_ble_control.cc").write_text(CPP, encoding="utf-8")
    cmake = MAIN / "CMakeLists.txt"
    content = cmake.read_text(encoding="utf-8")
    if "                        bt\n" not in content:
        raise RuntimeError("STOP: existing ESP NimBLE component missing")
    if "CONFIG_BT_NIMBLE_ENABLED=y" not in (ROOT / "upstream/firmware/sdkconfig.defaults").read_text():
        raise RuntimeError("STOP: BLE not enabled in pinned original")
    print("ARLO_BLE_V2_READY: new direct BLE head controller, app code 0000.")
    print("Original camera, voice, AI, menu and servo ranges preserved.")

if __name__ == "__main__":
    patch()
