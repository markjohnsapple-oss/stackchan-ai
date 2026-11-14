#pragma once
// AHL ASL Companion: user-command-only local memory with bounded vector recall.
// Never transmits, captures, logs or stores raw audio/images/face data.
// NVS namespace is separate from factory settings and the existing AHL brain.
#include "ahl_vector_index.h"
#include <nvs.h>
#include <cstdio>
#include <mutex>
#include <string>
#include <cctype>

namespace ahl {
class MemoryService {
public:
    enum class Command : uint8_t { None, Saved, Full, Cleared, Failed, LearningOn, LearningOff };
    Command processExplicitUtterance(const std::string& utterance) {
        std::string text = trim(utterance);
        const std::string lowered = lowerAscii(text);
        if (lowered == "start learning about me" || lowered == "enable learning") return setLearning(true);
        if (lowered == "stop learning about me" || lowered == "disable learning") return setLearning(false);
        if (lowered == "forget all companion memories" ||
            lowered == "forget everything i taught you") return eraseAll();
        const char* prefixes[] = {"remember that ", "please remember that ",
                                  "please remember ", "remember ",
                                  "learn that ", "please learn that ",
                                  "teach you that "};
        size_t prefix=0;
        for (const char* p:prefixes) {
            const std::string candidate=p;
            if (lowered.rfind(candidate,0)==0) { prefix=candidate.size(); break; }
        }
        if (!prefix) {
            // Opt-in only; never keep arbitrary transcripts or camera data.
            const char* starters[] = {"my name is ", "my favourite ", "my favorite ",
                                      "i enjoy ", "i like ", "i prefer ",
                                      "i am working on ", "i'm working on "};
            bool personal_fact = false;
            for (const char* p : starters) {
                if (lowered.rfind(p, 0) == 0) { personal_fact = true; break; }
            }
            if (!personal_fact) return Command::None;
            {
                std::lock_guard<std::mutex> guard(mutex_);
                if (!loadLocked() || !learning_enabled_) return Command::None;
            }
            const char* blocked[] = {"password", "passcode", "pin number", "credit card",
                                     "bank account", "address", "passport", "medical",
                                     "medication", "diagnos", "health", "secret key",
                                     "api key", "private key"};
            for (const char* word : blocked) {
                if (lowered.find(word) != std::string::npos) return Command::None;
            }
        }
        const std::string note = trim(text.substr(prefix));
        if (note.empty() || note.size()>VectorNoteIndex::MaxTextBytes ||
            note.find('\n')!=std::string::npos || note.find('\r')!=std::string::npos) return Command::Failed;
        std::lock_guard<std::mutex> guard(mutex_);
        if(!loadLocked())return Command::Failed;
        if(index_.size()>=VectorNoteIndex::MaxNotes)return Command::Full;
        // Duplicate notes are not written again. No automatic transcript ingestion.
        for(size_t i=0;i<index_.size();i++)if(index_.get(i)==note)return Command::Saved;
        nvs_handle_t h=0;
        if(nvs_open("ahl_notes_v1",NVS_READWRITE,&h)!=ESP_OK)return Command::Failed;
        char key[12]; std::snprintf(key,sizeof(key),"note%02u",static_cast<unsigned>(index_.size()));
        const bool written=nvs_set_str(h,key,note.c_str())==ESP_OK && nvs_commit(h)==ESP_OK;
        nvs_close(h);
        if(!written)return Command::Failed;
        index_.insert(note);
        return Command::Saved;
    }
    std::string search(const std::string& query) {
        std::lock_guard<std::mutex> guard(mutex_);
        if(!loadLocked())return "Memory unavailable";
        auto result=index_.nearest(query);
        return result.found ? result.text : "No matching user-approved memory";
    }
    size_t count() {
        std::lock_guard<std::mutex> guard(mutex_);
        return loadLocked()?index_.size():0;
    }
    std::string list(size_t max_items=8) {
        std::lock_guard<std::mutex> guard(mutex_);
        if (!loadLocked()) return "Memory unavailable";
        if (!index_.size()) return "No personal facts saved";
        std::string out = "Saved personal facts (" + std::to_string(index_.size()) + " total):";
        const size_t limit = index_.size() < max_items ? index_.size() : max_items;
        for (size_t i=0; i<limit; ++i) {
            out += "\n" + std::to_string(i+1) + ". " + index_.get(i);
        }
        if (limit < index_.size()) out += "\nMore facts saved; search for a particular topic.";
        return out;
    }
    std::string status() {
        std::lock_guard<std::mutex> guard(mutex_);
        if (!loadLocked()) return "Memory unavailable";
        return "Personal facts saved: " + std::to_string(index_.size()) +
               " of " + std::to_string(VectorNoteIndex::MaxNotes) +
               "; natural learning: " + (learning_enabled_ ? "ON" : "OFF") +
               ". Learning is stored locally and never keeps raw speech or photographs.";
    }
    Command eraseAll() {
        std::lock_guard<std::mutex> guard(mutex_);
        nvs_handle_t h=0;
        auto error=nvs_open("ahl_notes_v1",NVS_READWRITE,&h);
        if(error!=ESP_OK)return Command::Failed;
        error=nvs_erase_all(h);
        if(error==ESP_OK)error=nvs_commit(h);
        nvs_close(h);
        if(error!=ESP_OK)return Command::Failed;
        index_.clear(); loaded_=true; learning_enabled_=false;
        return Command::Cleared;
    }
private:
    std::mutex mutex_;
    VectorNoteIndex index_;
    bool loaded_=false;
    bool learning_enabled_=false;
    Command setLearning(bool enabled) {
        std::lock_guard<std::mutex> guard(mutex_);
        if (!loadLocked()) return Command::Failed;
        nvs_handle_t h=0;
        if (nvs_open("ahl_notes_v1",NVS_READWRITE,&h)!=ESP_OK) return Command::Failed;
        const bool saved=nvs_set_u8(h,"learn",enabled?1:0)==ESP_OK &&
                         nvs_commit(h)==ESP_OK;
        nvs_close(h);
        if (!saved) return Command::Failed;
        learning_enabled_=enabled;
        return enabled?Command::LearningOn:Command::LearningOff;
    }
    static std::string lowerAscii(std::string text) {
        for(char& c:text){auto u=static_cast<unsigned char>(c);if(u<128)c=static_cast<char>(std::tolower(u));}
        return text;
    }
    static std::string trim(const std::string& s) {
        auto first=s.find_first_not_of(" \t\r\n");
        if(first==std::string::npos)return {};
        auto last=s.find_last_not_of(" \t\r\n");
        return s.substr(first,last-first+1);
    }
    bool loadLocked() {
        if(loaded_)return true;
        nvs_handle_t h=0;
        auto error=nvs_open("ahl_notes_v1",NVS_READONLY,&h);
        if(error==ESP_ERR_NVS_NOT_FOUND){loaded_=true;return true;}
        if(error!=ESP_OK)return false;
        uint8_t learn=0;
        if(nvs_get_u8(h,"learn",&learn)==ESP_OK) learning_enabled_=(learn==1);
        VectorNoteIndex temp;
        for(size_t i=0;i<VectorNoteIndex::MaxNotes;i++) {
            char key[12];std::snprintf(key,sizeof(key),"note%02u",static_cast<unsigned>(i));
            size_t len=0;
            if(nvs_get_str(h,key,nullptr,&len)!=ESP_OK)break;
            if(len<2 || len>VectorNoteIndex::MaxTextBytes+1)break;
            std::string note(len,'\0');
            if(nvs_get_str(h,key,note.data(),&len)!=ESP_OK)break;
            note.resize(len-1);
            if(!temp.insert(note))break;
        }
        nvs_close(h);
        index_=std::move(temp);loaded_=true;
        return true;
    }
};
inline MemoryService& getAslMemory() { static MemoryService service; return service; }
}