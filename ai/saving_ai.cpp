// saving_ai.cpp — 세이빙 AI 의도 판단기 C++ 실행기 (2026-10-20) · 외부 라이브러리 없음 · Linux/Windows 공용
//
//   입력 = rules.py 가 숫자 자리를 표시 기호(ⓜⓡⓟⓓⓢ)로 바꾼 문장 한 줄 (UTF-8)
//   → 한글을 초성·중성·종성 자모로 나눔 (tok.py 와 같다) → int8 양방향 인코더 한 번 → <cls> 자리에서 의도 7가지
//   계산 규칙은 train.py int8 모드와 같다: 가중치 행마다 int8 · 입력 벡터마다 int8 · 곱의 합은 정수(int32)
//                                       LayerNorm · GELU · softmax 는 float32
//
//   Linux  : g++ -O2 -std=c++17 -o saving_ai saving_ai.cpp
//   Windows: cl /O2 /EHsc /utf-8 saving_ai.cpp      또는  g++ -O2 -std=c++17 -static -o saving_ai.exe saving_ai.cpp
//   ./saving_ai saving_ai.bin                 # 표준입력 한 줄 → "의도<TAB>확신도<TAB>7개 확률(쉼표)"
//   ./saving_ai saving_ai.bin --bench 1000
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <string>
#include <vector>
#include <unordered_map>
#include <algorithm>
#include <chrono>
#include <iostream>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
using namespace std;

struct Mat { int r = 0, c = 0; vector<int8_t> q; vector<float> s; };
struct Layer { vector<float> l1w, l1b, l2w, l2b, bqkv, bo, b1, b2; Mat qkv, o, f1, f2; };
struct Model {
    uint32_t d, L, h, ff, ctx, V, nint;
    vector<string> vocab, intents; unordered_map<string, int> stoi;
    Mat tok, pos, hi; vector<float> bi; vector<Layer> lay; vector<float> lfw, lfb;
};
static const uint8_t *P;
template <class T> static T rd() { T v; memcpy(&v, P, sizeof(T)); P += sizeof(T); return v; }
static vector<float> rdv(int n) { vector<float> v(n); memcpy(v.data(), P, 4 * (size_t)n); P += 4 * (size_t)n; return v; }
static Mat rdm(int r, int c) { Mat m; m.r = r; m.c = c; m.q.resize((size_t)r * c); memcpy(m.q.data(), P, (size_t)r * c); P += (size_t)r * c; m.s = rdv(r); return m; }
static string rds() { int n = rd<uint8_t>(); string s((const char *)P, n); P += n; return s; }

static bool load(const char *fn, Model &M, vector<uint8_t> &buf) {
    FILE *f = fopen(fn, "rb"); if (!f) return false;
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET); buf.resize(n);
    if (fread(buf.data(), 1, n, f) != (size_t)n) { fclose(f); return false; } fclose(f);
    P = buf.data(); if (memcmp(P, "SAB1", 4)) return false; P += 4;
    M.d = rd<uint32_t>(); M.L = rd<uint32_t>(); M.h = rd<uint32_t>(); M.ff = rd<uint32_t>(); M.ctx = rd<uint32_t>();
    M.V = rd<uint32_t>(); M.nint = rd<uint32_t>();
    for (uint32_t i = 0; i < M.V; i++) { M.vocab.push_back(rds()); M.stoi[M.vocab.back()] = i; }
    for (uint32_t i = 0; i < M.nint; i++) M.intents.push_back(rds());
    int d = M.d, F = M.ff * M.d;
    M.tok = rdm(M.V, d); M.pos = rdm(M.ctx, d);
    for (uint32_t i = 0; i < M.L; i++) {
        Layer Ly; Ly.l1w = rdv(d); Ly.l1b = rdv(d);
        Ly.qkv = rdm(3 * d, d); Ly.bqkv = rdv(3 * d); Ly.o = rdm(d, d); Ly.bo = rdv(d);
        Ly.l2w = rdv(d); Ly.l2b = rdv(d);
        Ly.f1 = rdm(F, d); Ly.b1 = rdv(F); Ly.f2 = rdm(d, F); Ly.b2 = rdv(d);
        M.lay.push_back(std::move(Ly));
    }
    M.lfw = rdv(d); M.lfb = rdv(d);
    M.hi = rdm(M.nint, d); M.bi = rdv(M.nint);
    return (size_t)(P - buf.data()) == buf.size();
}

// y = int8(x) · int8(W)ᵀ (정수 합) × s × ws + b      (반올림 = 짝수 쪽, torch.round 와 같다)
static inline float rne(float v) { float r = nearbyintf(v); return r; }
static void lin(const float *x, int n, const Mat &W, const float *b, float *y) {
    float mx = 0; for (int i = 0; i < n; i++) mx = max(mx, fabsf(x[i]));
    float s = max(mx / 127.0f, 1e-8f);
    static thread_local vector<int8_t> xq; xq.resize(n);
    for (int i = 0; i < n; i++) { float v = rne(x[i] / s); xq[i] = (int8_t)max(-127.0f, min(127.0f, v)); }
    for (int r = 0; r < W.r; r++) {
        const int8_t *w = &W.q[(size_t)r * n]; int32_t acc = 0;
        for (int i = 0; i < n; i++) acc += (int32_t)xq[i] * w[i];
        y[r] = (float)acc * s * W.s[r] + b[r];
    }
}
static void lnorm(const float *x, int n, const float *w, const float *b, float *y) {
    float m = 0; for (int i = 0; i < n; i++) m += x[i]; m /= n;
    float v = 0; for (int i = 0; i < n; i++) v += (x[i] - m) * (x[i] - m); v /= n;
    float r = 1.0f / sqrtf(v + 1e-5f);
    for (int i = 0; i < n; i++) y[i] = (x[i] - m) * r * w[i] + b[i];
}

// ═════════ 자모 나누기 (tok.jamo 와 같다) ═════════
static void put_cp(string &o, uint32_t c) {
    if (c < 0x80) o += (char)c;
    else if (c < 0x800) { o += (char)(0xC0 | (c >> 6)); o += (char)(0x80 | (c & 63)); }
    else if (c < 0x10000) { o += (char)(0xE0 | (c >> 12)); o += (char)(0x80 | ((c >> 6) & 63)); o += (char)(0x80 | (c & 63)); }
    else { o += (char)(0xF0 | (c >> 18)); o += (char)(0x80 | ((c >> 12) & 63)); o += (char)(0x80 | ((c >> 6) & 63)); o += (char)(0x80 | (c & 63)); }
}
static vector<string> jamo(const string &s) {
    vector<string> out;
    for (size_t i = 0; i < s.size();) {
        unsigned char c0 = s[i]; uint32_t c; size_t n;
        if (c0 < 0x80) { c = c0; n = 1; }
        else if ((c0 >> 5) == 6) { c = c0 & 31; n = 2; }
        else if ((c0 >> 4) == 14) { c = c0 & 15; n = 3; }
        else { c = c0 & 7; n = 4; }
        for (size_t k = 1; k < n && i + k < s.size(); k++) c = (c << 6) | (s[i + k] & 63);
        i += n;
        string o;
        if (c >= 0xAC00 && c <= 0xD7A3) {
            uint32_t k = c - 0xAC00;
            put_cp(o, 0x1100 + k / 588); out.push_back(o); o.clear();
            put_cp(o, 0x1161 + (k % 588) / 28); out.push_back(o); o.clear();
            if (k % 28) { put_cp(o, 0x11A8 + k % 28 - 1); out.push_back(o); }
            continue;
        }
        if (c == '\t' || c == '\n' || c == '\r' || c == 0x3000) c = ' ';
        if (c >= 'A' && c <= 'Z') c += 32;
        put_cp(o, c); out.push_back(o);
    }
    return out;
}

// → 의도 번호 · 확률들
static int judge(const Model &M, const string &text, vector<float> &prob) {
    vector<int> ids{M.stoi.at("<cls>")};
    int unk = M.stoi.at("<unk>");
    for (auto &t : jamo(text)) { auto it = M.stoi.find(t); ids.push_back(it == M.stoi.end() ? unk : it->second); }
    if (ids.size() > M.ctx) ids.resize(M.ctx);
    int d = M.d, H = M.h, hd = d / H, F = M.ff * d, T = ids.size();
    vector<float> x((size_t)T * d), a(d), qkv((size_t)T * 3 * d), att((size_t)T * d), f(F), t2(d), p(T);
    for (int t = 0; t < T; t++)
        for (int i = 0; i < d; i++)
            x[(size_t)t * d + i] = (float)M.tok.q[(size_t)ids[t] * d + i] * M.tok.s[ids[t]] + (float)M.pos.q[(size_t)t * d + i] * M.pos.s[t];
    float sc = 1.0f / sqrtf((float)hd);
    for (uint32_t l = 0; l < M.L; l++) {
        const Layer &Ly = M.lay[l];
        for (int t = 0; t < T; t++) { lnorm(&x[(size_t)t * d], d, Ly.l1w.data(), Ly.l1b.data(), a.data()); lin(a.data(), d, Ly.qkv, Ly.bqkv.data(), &qkv[(size_t)t * 3 * d]); }
        for (int t = 0; t < T; t++)
            for (int hh = 0; hh < H; hh++) {
                const float *q = &qkv[(size_t)t * 3 * d + hh * hd]; float mx = -1e30f;
                for (int j = 0; j < T; j++) { const float *k = &qkv[(size_t)j * 3 * d + d + hh * hd]; float s = 0; for (int e = 0; e < hd; e++) s += q[e] * k[e]; p[j] = s * sc; mx = max(mx, p[j]); }
                float z = 0; for (int j = 0; j < T; j++) { p[j] = expf(p[j] - mx); z += p[j]; }
                for (int e = 0; e < hd; e++) { float s = 0; for (int j = 0; j < T; j++) s += p[j] * qkv[(size_t)j * 3 * d + 2 * d + hh * hd + e]; att[(size_t)t * d + hh * hd + e] = s / z; }
            }
        for (int t = 0; t < T; t++) {
            float *xt = &x[(size_t)t * d];
            lin(&att[(size_t)t * d], d, Ly.o, Ly.bo.data(), t2.data()); for (int i = 0; i < d; i++) xt[i] += t2[i];
            lnorm(xt, d, Ly.l2w.data(), Ly.l2b.data(), a.data());
            lin(a.data(), d, Ly.f1, Ly.b1.data(), f.data());
            for (int i = 0; i < F; i++) f[i] = 0.5f * f[i] * (1.0f + erff(f[i] / sqrtf(2.0f)));
            lin(f.data(), F, Ly.f2, Ly.b2.data(), t2.data()); for (int i = 0; i < d; i++) xt[i] += t2[i];
        }
    }
    lnorm(&x[0], d, M.lfw.data(), M.lfb.data(), a.data());      // <cls> 자리만 쓴다
    vector<float> li(M.nint); lin(a.data(), d, M.hi, M.bi.data(), li.data());
    int best = max_element(li.begin(), li.end()) - li.begin();
    float z = 0; prob.assign(M.nint, 0);
    for (uint32_t i = 0; i < M.nint; i++) { prob[i] = expf(li[i] - li[best]); z += prob[i]; }
    for (auto &v : prob) v /= z;
    return best;
}

int main(int argc, char **argv) {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY); _setmode(_fileno(stdout), _O_BINARY);   // 줄 끝 \r\n 바꿈 막기 (UTF-8 바이트 그대로)
#endif
    if (argc < 2) { fprintf(stderr, "usage: %s saving_ai.bin [--bench N]\n", argv[0]); return 1; }
    Model M; vector<uint8_t> buf;
    if (!load(argv[1], M, buf)) { fprintf(stderr, "model load failed\n"); return 1; }
    vector<float> pr;
    if (argc >= 4 && string(argv[2]) == "--bench") {
        int n = atoi(argv[3]);
        string tx = "공사비 ⓜ, ⓟ 안에 회수하고 싶어요";
        auto t0 = chrono::steady_clock::now(); int b = 0;
        for (int i = 0; i < n; i++) b = judge(M, tx, pr);
        double ms = chrono::duration<double, milli>(chrono::steady_clock::now() - t0).count() / n;
        printf("%s %.4f\n%.3f ms per sentence (1 core, %d runs avg)\n", M.intents[b].c_str(), pr[b], ms, n);
        return 0;
    }
    string line;
    while (getline(cin, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        int b = judge(M, line, pr);
        printf("%s\t%.4f\t", M.intents[b].c_str(), pr[b]);
        for (size_t i = 0; i < pr.size(); i++) printf(i ? ",%.4f" : "%.4f", pr[i]);
        printf("\n"); fflush(stdout);
    }
}
