#pragma once
// AHL local, bounded hashed-vector note index. This does not use cloud embeddings.
// Stores no user information by itself; persistence is provided by a separate opt-in layer.
#include <array>
#include <cmath>
#include <cctype>
#include <cstdint>
#include <string>
#include <vector>

namespace ahl {
class VectorNoteIndex {
public:
    static constexpr size_t Dim = 64;
    static constexpr size_t MaxNotes = 16;
    static constexpr size_t MaxTextBytes = 160;
    struct Match { std::string text; float similarity = 0.f; bool found = false; };

    bool insert(const std::string& text) {
        if(text.empty() || text.size()>MaxTextBytes || entries_.size()>=MaxNotes) return false;
        if(text.find('\0')!=std::string::npos || text.find('\n')!=std::string::npos || text.find('\r')!=std::string::npos) return false;
        for(const auto& e:entries_) if(e.text==text) return false;
        entries_.push_back({text, vectorize(text)});
        return true;
    }
    void clear() { entries_.clear(); }
    size_t size() const { return entries_.size(); }
    const std::string& get(size_t index) const { return entries_.at(index).text; }
    Match nearest(const std::string& query, float minSimilarity=0.16f) const {
        const auto q=vectorize(query);
        Match best;
        for(const auto& e:entries_){
            float sim=0;
            for(size_t k=0;k<Dim;k++)sim+=q[k]*e.features[k];
            if(sim>best.similarity){best={e.text,sim,true};}
        }
        if(!best.found || best.similarity<minSimilarity) return {};
        return best;
    }
private:
    using Vec=std::array<float,Dim>;
    struct Entry { std::string text; Vec features; };
    std::vector<Entry> entries_;
    static uint32_t hash(const char* str,size_t n){
        uint32_t h=2166136261u;
        for(size_t i=0;i<n;i++){h^=static_cast<uint8_t>(str[i]);h*=16777619u;}
        return h;
    }
    static Vec vectorize(const std::string& text){
        Vec v{};
        std::string s;
        s.reserve(text.size());
        for(unsigned char c:text){
            if(c<128){
                char d=static_cast<char>(std::tolower(c));
                s.push_back(std::isalnum(c)?d:' ');
            }
        }
        size_t start=0;
        while(start<s.size()){
            while(start<s.size() && s[start]==' ')start++;
            const size_t begin=start;
            while(start<s.size() && s[start]!=' ')start++;
            const size_t n=start-begin;
            if(n==0)continue;
            uint32_t h=hash(s.data()+begin,n);
            v[h%Dim]+=2.f;
            if(n>=3){
                for(size_t i=0;i+3<=n;i++){
                    h=hash(s.data()+begin+i,3);
                    v[h%Dim]+=0.15f;
                }
            }
        }
        float sum=0;
        for(float x:v)sum+=x*x;
        if(sum>0){float scale=1.f/std::sqrt(sum);for(float& x:v)x*=scale;}
        return v;
    }
};
}