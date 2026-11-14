#!/usr/bin/env python3
"""Add a PIN-paired ARLO head-control page after network readiness (boot-safe v2).

Builds the smartphone-friendly HTML into the firmware and also ships the same
HTML as a standalone controller. No change to AI audio, camera or wake-free
conversation code. Uses existing manufacturer motor limits and LVGL mutex.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "upstream/firmware/main"
HAL = MAIN / "hal"
CMAKE = MAIN / "CMakeLists.txt"
HAL_CPP = HAL / "hal.cpp"
HTML = ROOT / "controller/ARLO_Head_Control_v1.html"
PAGE_HEADER = HAL / "arlo_head_page.h"
SOURCE = HAL / "arlo_head_control.cc"

def once(text, before, after, label):
    n = text.count(before)
    if n != 1:
        raise RuntimeError(f"STOP: unexpected {label} in pinned source: {n} matches")
    return text.replace(before, after, 1)

CPP = r'''
// ARLO Head Control v1: optional, short-lived, PIN-paired Wi-Fi joystick.
// Standalone service on TCP 8765, no public cloud, no new AI subsystem.
// Safe movement is yaw +/-25 deg, pitch 5..30 deg, speed 150.
// Built from source; no NVS writes and no existing functionality changed.
#include "hal.h"
#include "arlo_head_page.h"
#include <stackchan/stackchan.h>
#include <application.h>
#include <board.h>
#include <display.h>
#include <esp_http_server.h>
#include <esp_log.h>
#include <esp_random.h>
#include <esp_timer.h>
#include <cJSON.h>
#include <cstdio>
#include <cstring>
#include <string>

namespace {
static const char* TAG = "ARLO_HEAD";
static httpd_handle_t server = nullptr;
static uint32_t pin_code = 0;
static int64_t pin_expiry = 0;
static int64_t last_pair_screen = 0;
static int64_t last_move = 0;

static void cors(httpd_req_t* req) {
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Headers", "Content-Type, X-ARLO-PIN");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Private-Network", "true");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
}
static esp_err_t json(httpd_req_t* req, const char* body, const char* status = "200 OK") {
    cors(req);
    httpd_resp_set_status(req, status);
    httpd_resp_set_type(req, "application/json");
    return httpd_resp_send(req, body, HTTPD_RESP_USE_STRLEN);
}
static esp_err_t options(httpd_req_t* req) {
    cors(req);
    return httpd_resp_send(req, "", 0);
}
static bool authorised(httpd_req_t* req) {
    const int64_t now = esp_timer_get_time();
    if (pin_code == 0 || now >= pin_expiry) return false;
    char value[16] = {};
    const size_t length = httpd_req_get_hdr_value_len(req, "X-ARLO-PIN");
    if (length != 6 || httpd_req_get_hdr_value_str(req, "X-ARLO-PIN", value, sizeof(value)) != ESP_OK)
        return false;
    char expected[8] = {};
    std::snprintf(expected, sizeof(expected), "%06lu", static_cast<unsigned long>(pin_code));
    // Fixed six-digit comparison; never print or return the code over Wi-Fi.
    unsigned mismatch = 0;
    for (int i = 0; i < 6; ++i) mismatch |= static_cast<unsigned>(value[i] ^ expected[i]);
    return mismatch == 0;
}
static esp_err_t page(httpd_req_t* req) {
    cors(req);
    httpd_resp_set_type(req, "text/html; charset=utf-8");
    return httpd_resp_send(req, ARLO_HEAD_PAGE, HTTPD_RESP_USE_STRLEN);
}
static esp_err_t pair(httpd_req_t* req) {
    const int64_t now = esp_timer_get_time();
    if (pin_code == 0 || now > pin_expiry) {
        pin_code = 100000u + esp_random() % 900000u;
        pin_expiry = now + 300000000LL;  // PIN valid for 5 minutes.
    }
    if (last_pair_screen == 0 || now - last_pair_screen > 3000000LL) {
        last_pair_screen = now;
        char message[80] = {};
        std::snprintf(message, sizeof(message), "ARLO head pairing code: %06lu",
                      static_cast<unsigned long>(pin_code));
        // Use the manufacturer's native UI event loop; never draw from httpd.
        Application::GetInstance().Schedule([value = std::string(message)]() {
            Board::GetInstance().GetDisplay()->ShowNotification(value.c_str(), 18000);
        });
        ESP_LOGI(TAG, "Pair requested: showing code on robot display");
    }
    return json(req, "{\"ok\":true}");
}
static esp_err_t test(httpd_req_t* req) {
    if (!authorised(req)) return json(req, "{\"ok\":false,\"error\":\"Invalid or expired code. Tap Pair again.\"}", "403 Forbidden");
    return json(req, "{\"ok\":true,\"name\":\"ARLO\",\"mode\":\"head\"}");
}
static esp_err_t move(httpd_req_t* req) {
    if (!authorised(req)) return json(req, "{\"ok\":false,\"error\":\"Invalid or expired code. Tap Pair again.\"}", "403 Forbidden");
    if (req->content_len == 0 || req->content_len > 127)
        return json(req, "{\"ok\":false,\"error\":\"Invalid movement request\"}", "400 Bad Request");
    char body[128] = {};
    const int count = httpd_req_recv(req, body, req->content_len);
    if (count != static_cast<int>(req->content_len))
        return json(req, "{\"ok\":false,\"error\":\"Incomplete movement request\"}", "400 Bad Request");
    cJSON* doc = cJSON_ParseWithLength(body, static_cast<size_t>(count));
    if (!doc) return json(req, "{\"ok\":false,\"error\":\"Invalid JSON\"}", "400 Bad Request");
    const cJSON* y = cJSON_GetObjectItemCaseSensitive(doc, "yaw");
    const cJSON* p = cJSON_GetObjectItemCaseSensitive(doc, "pitch");
    bool ok = cJSON_IsNumber(y) && cJSON_IsNumber(p);
    const int yaw = ok ? y->valueint : 0;
    const int pitch = ok ? p->valueint : 0;
    ok = ok && yaw >= -25 && yaw <= 25 && pitch >= 5 && pitch <= 30
            && y->valuedouble == static_cast<double>(yaw)
            && p->valuedouble == static_cast<double>(pitch);
    cJSON_Delete(doc);
    if (!ok) return json(req, "{\"ok\":false,\"error\":\"Head angle outside safe range\"}", "400 Bad Request");

    // Maximum ~8 updates/sec. No extra motor task or timer is created.
    const int64_t now = esp_timer_get_time();
    if (now - last_move < 110000LL)
        return json(req, "{\"ok\":true,\"rate_limited\":true}");
    last_move = now;
    {
        LvglLockGuard lock;
        GetStackChan().motion().moveWithSpeed(yaw * 10, pitch * 10, 150);
    }
    return json(req, "{\"ok\":true}");
}
static esp_err_t stop(httpd_req_t* req) {
    if (!authorised(req)) return json(req, "{\"ok\":false,\"error\":\"Invalid or expired code. Tap Pair again.\"}", "403 Forbidden");
    {
        LvglLockGuard lock;
        GetStackChan().motion().stop();
    }
    return json(req, "{\"ok\":true}");
}
static bool endpoint(const char* uri, httpd_method_t method, esp_err_t (*handler)(httpd_req_t*)) {
    httpd_uri_t descriptor = {};
    descriptor.uri = uri;
    descriptor.method = method;
    descriptor.handler = handler;
    descriptor.user_ctx = nullptr;
    return httpd_register_uri_handler(server, &descriptor) == ESP_OK;
}
}  // namespace

void arlo_head_control_http_start() {
    if (server) return;
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 8765;
    config.max_uri_handlers = 10;
    config.max_open_sockets = 3;
    config.stack_size = 6144;
    config.lru_purge_enable = true;
    esp_err_t err = httpd_start(&server, &config);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "Unable to start local joystick HTTP server: %s", esp_err_to_name(err));
        return;
    }
    bool ok = endpoint("/", HTTP_GET, page)
        && endpoint("/arlo/pair", HTTP_POST, pair)
        && endpoint("/arlo/test", HTTP_POST, test)
        && endpoint("/arlo/move", HTTP_POST, move)
        && endpoint("/arlo/stop", HTTP_POST, stop)
        && endpoint("/arlo/pair", HTTP_OPTIONS, options)
        && endpoint("/arlo/test", HTTP_OPTIONS, options)
        && endpoint("/arlo/move", HTTP_OPTIONS, options)
        && endpoint("/arlo/stop", HTTP_OPTIONS, options);
    if (!ok) {
        ESP_LOGE(TAG, "HTTP control route registration failed; disabling joystick");
        httpd_stop(server);
        server = nullptr;
    } else {
        ESP_LOGI(TAG, "ARLO head control active on local Wi-Fi TCP port 8765; pair at robot screen");
    }
}
'''

def patch():
    page = HTML.read_text(encoding="utf-8")
    if "<!doctype html>" not in page.lower() or '/arlo/move' not in page or '</html>' not in page:
        raise RuntimeError("STOP: missing or damaged ARLO joystick page")
    if ')ARLO_PAGE"' in page:
        raise RuntimeError("STOP: raw HTML conflicts with C++ string delimiter")
    PAGE_HEADER.write_text(
        '#pragma once\n// Generated verbatim from the downloadable ARLO HTML.\n'
        'static const char ARLO_HEAD_PAGE[] = R"ARLO_PAGE(\n'
        + page + '\n)ARLO_PAGE";\n', encoding="utf-8")
    SOURCE.write_text(CPP, encoding="utf-8")

    # The original Hal::startXiaozhi must NOT start an HTTP server here:
    # XiaoZhi has not initialised its network stack at that point.
    # Keep Hal unchanged. Hook only the existing network-connected event.
    application_cpp = ROOT / "upstream/firmware/xiaozhi-esp32/main/application.cc"
    native = application_cpp.read_text(encoding="utf-8")
    native = once(
        native,
        'void Application::HandleNetworkConnectedEvent() {\n'
        '    ahl_network_online_ = true;\n'
        '    ESP_LOGI(TAG, "Network connected");',
        'void arlo_head_control_http_start();\n\n'
        'void Application::HandleNetworkConnectedEvent() {\n'
        '    ahl_network_online_ = true;\n'
        '    ESP_LOGI(TAG, "Network connected");\n'
        '    // ARLO: start the optional joystick only once networking is online.\n'
        '    arlo_head_control_http_start();',
        "network-connected joystick startup")
    application_cpp.write_text(native, encoding="utf-8")

    cmake = CMAKE.read_text(encoding="utf-8")
    cmake = once(cmake, '                        esp_http_client\n',
                '                        esp_http_client\n                        esp_http_server\n',
                'HTTP server dependency')
    CMAKE.write_text(cmake, encoding="utf-8")
    print("ARLO_HEAD_CONTROL_V2_READY: network-ready HTTP server with six-digit PIN.")
    print("Original HAL startup unchanged; XiaoZhi network-ready event triggers optional HTTP.")
    print("Rate-limited commands, physical PIN display, narrow test angles and STOP.")
    print("Web page at http://<ARLO-WIFI-IP>:8765/ (or standalone HTML via the same Wi-Fi).")
    print("Motion requires real-device testing with the new humanoid body.")

if __name__ == "__main__":
    patch()
