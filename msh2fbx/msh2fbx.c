/*
 * msh2fbx — Star Conflict .mdl-mshXXX → FBX converter (standalone C)
 * ====================================================================
 * 将 Hammer Engine 的 .mdl-msh000~1308 静态网格转换为 Autodesk FBX。
 * 依赖：ufbx_write (MIT, bqqbarbhg/ufbx_write)
 *
 * 用法：
 *   msh2fbx model.mdl-msh000
 *   msh2fbx model.mdl-msh000 output.fbx
 *   msh2fbx --batch input_dir output_dir
 *   msh2fbx --batch input_dir output_dir --workers 8
 *
 * 命名规则（与 Noesis 管道一致）：
 *   plasma_gun_mod1.mdl-msh000 → plasma_gun_mod1000.fbx
 *
 * 编译（MSVC）：
 *   cl /O2 /nologo /Fe:msh2fbx.exe /DUFBXW_STATIC msh2fbx.c ufbx_write.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>

#ifdef _WIN32
  #define WIN32_LEAN_AND_MEAN
  #define _CRT_SECURE_NO_WARNINGS
  #include <windows.h>
  #define PATH_SEP '\\'
#else
  #include <limits.h>
  #include <unistd.h>
  #define PATH_SEP '/'
  #define MAX_PATH 4096
#endif

#ifndef UFBXW_STATIC
  #define UFBXW_STATIC
#endif
#include "ufbx_write.h"

/* =========================================================================
 * MSH 格式定义
 * ========================================================================= */

/* 顶点字节数（VBytes）和对应的 UV 偏移 */
static int get_uv_offset(uint32_t vbytes, uint32_t flag)
{
    switch (vbytes) {
        case 20: return 12;   /* pos@0(12B), UV@12(8B) */
        case 24: return 16;   /* pos@0(12B), ?(4B), UV@16(8B) */
        case 28:
            if (flag == 0xE) return 16;
            if (flag == 5 || flag == 0x11) return 20;  /* flag=5 UV at 20 (verified: pvp_omega skybox) */
            return 16;
        case 32:
            if (flag == 0x0F) return 16;   /* Fixed: was 20, UV1 at offset 16 (fed_mercenary_tool) */
            return 20;
        case 36: return 20;
        case 40:
            if (flag == 0x13) return 20;   /* Fixed: was 24, UV1 at offset 20 (loader, reptile_01) */
            if (flag == 0x10) return 16;   /* Fixed: was 24, UV1 at offset 16 (skinned: fed_mercenary_man) */
            return 24;
        case 44: return 20;   /* VBytes=44: UV1 at offset 20 (not 24) */
        default: return -1;   /* unknown layout, export position only */
    }
}

/* UV2 格式枚举 */
typedef enum { UV2_NONE, UV2_FLOAT2, UV2_UINT16_UNORM } uv2_format_t;

/* 获取 UV2 (lightmap) 的字节偏移和格式。
   返回 (offset, format)，如无 UV2 空间则 format=UV2_NONE。 */
static void get_uv2_info(uint32_t vbytes, uint32_t flag, int *out_offset, uv2_format_t *out_format)
{
    *out_format = UV2_NONE;
    *out_offset = -1;

    /* VBytes=28 flag=0x0E: FX UV2 for animated_mock airwalls/gates */
    if (vbytes == 28 && flag == 0x0E) {
        *out_offset = 24;
        *out_format = UV2_UINT16_UNORM;
        return;
    }

    if (vbytes < 36) return;  /* 无 UV2 空间 */

    if (vbytes == 36) {
        *out_offset = 28;
        *out_format = UV2_UINT16_UNORM;  /* VBytes=36: UV2 is uint16 UNORM, not float2 */
    } else if (vbytes == 40) {
        *out_offset = 32;
        if (flag == 0x1C || flag == 0x10)
            *out_format = UV2_UINT16_UNORM;
        else if (flag == 0x13)
            *out_format = UV2_FLOAT2;
        else
            *out_format = UV2_FLOAT2;
    } else if (vbytes == 44) {
        *out_offset = 28;
        *out_format = UV2_UINT16_UNORM;
    }
}

/* =========================================================================
 * 顶点法线计算 — 平均相邻面法线
 * ========================================================================= */

static void compute_vertex_normals(const float *positions, const int32_t *indices,
                                   uint32_t vcount, uint32_t icount,
                                   float *out_normals)
{
    memset(out_normals, 0, vcount * 3 * sizeof(float));

    for (uint32_t i = 0; i < icount; i += 3) {
        int32_t i0 = indices[i+0], i1 = indices[i+1], i2 = indices[i+2];
        if (i0 < 0 || i1 < 0 || i2 < 0 ||
            (uint32_t)i0 >= vcount || (uint32_t)i1 >= vcount || (uint32_t)i2 >= vcount)
            continue;

        float e1x = positions[i0*3+0] - positions[i1*3+0];
        float e1y = positions[i0*3+1] - positions[i1*3+1];
        float e1z = positions[i0*3+2] - positions[i1*3+2];
        float e2x = positions[i2*3+0] - positions[i1*3+0];
        float e2y = positions[i2*3+1] - positions[i1*3+1];
        float e2z = positions[i2*3+2] - positions[i1*3+2];

        float nx = e1y*e2z - e1z*e2y;
        float ny = e1z*e2x - e1x*e2z;
        float nz = e1x*e2y - e1y*e2x;
        float len = sqrtf(nx*nx + ny*ny + nz*nz);
        if (len < 1e-10f) continue;
        nx /= len; ny /= len; nz /= len;

        out_normals[i0*3+0] += nx; out_normals[i0*3+1] += ny; out_normals[i0*3+2] += nz;
        out_normals[i1*3+0] += nx; out_normals[i1*3+1] += ny; out_normals[i1*3+2] += nz;
        out_normals[i2*3+0] += nx; out_normals[i2*3+1] += ny; out_normals[i2*3+2] += nz;
    }

    for (uint32_t i = 0; i < vcount; i++) {
        float nx = out_normals[i*3+0], ny = out_normals[i*3+1], nz = out_normals[i*3+2];
        float len = sqrtf(nx*nx + ny*ny + nz*nz);
        if (len > 1e-10f) {
            out_normals[i*3+0] = nx/len; out_normals[i*3+1] = ny/len; out_normals[i*3+2] = nz/len;
        } else {
            out_normals[i*3+0] = 0.0f; out_normals[i*3+1] = 1.0f; out_normals[i*3+2] = 0.0f;
        }
    }
}

/* =========================================================================
 * MDF 材质名解析
 * ========================================================================= */

static int find_mdf_for_msh(const char *msh_path, char *out_mdf_path, size_t out_size)
{
    char base[MAX_PATH];
    {
        const char *fname = strrchr(msh_path, PATH_SEP);
        fname = fname ? fname + 1 : msh_path;
        const char *dot = strstr(fname, ".mdl-msh");
        if (dot) {
            size_t len = (size_t)(dot - fname);
            memcpy(base, fname, len); base[len] = '\0';
        } else {
            snprintf(base, sizeof(base), "%s", fname);
        }
    }
    const char *sep = strrchr(msh_path, PATH_SEP);
    size_t dir_len = sep ? (size_t)(sep - msh_path + 1) : 0;
    snprintf(out_mdf_path, out_size, "%.*s%s.mdf", (int)dir_len, msh_path, base);
    FILE *fp = fopen(out_mdf_path, "r");
    if (fp) { fclose(fp); return 1; }
    return 0;
}

static int parse_mdf_material_name(const char *mdf_path, char *out_name, size_t out_size)
{
    FILE *fp = fopen(mdf_path, "r");
    if (!fp) return 0;
    char line[1024];
    while (fgets(line, sizeof(line), fp)) {
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '/' || *p == '\n' || *p == '\r' || *p == '\0') continue;
        if (strncmp(p, "material", 8) == 0 && (p[8] == ' ' || p[8] == '\t')) {
            p += 8;
            while (*p == ' ' || *p == '\t') p++;
            char *end = p;
            while (*end != ' ' && *end != '\t' && *end != '\n' && *end != '\r' && *end != '\0') end++;
            size_t len = (size_t)(end - p);
            if (len > 0 && len < out_size) {
                memcpy(out_name, p, len); out_name[len] = '\0';
                fclose(fp); return 1;
            }
        }
    }
    fclose(fp);
    return 0;
}

/*
 * 解析 .mdl-mshXXX 文件。
 *
 * 文件结构（小端序）：
 *   [0x00] uint32 version   — 格式版本 (0/1/2/3)
 *   [0x04] uint32 flag      — 标记，影响 UV 偏移
 *   [0x08] uint32 VBytes    — 每顶点字节数 (20/24/28/32/36/40)
 *   [0x0C] uint32 VCount    — 顶点数
 *   [0x10] uint32 FCount    — 面索引数（三角形 ×3）
 *   [0x14~0x43]             — 保留/未知
 *   [0x44]                  — 顶点数据开始
 *   [0x44 + VCount*VBytes]  — 索引数据开始 (uint16 × FCount)
 *
 * 返回值：0 成功，-1 格式错误
 */
static int parse_msh(const uint8_t *data, size_t size,
                     float **out_positions,  /* [vcount*3] */
                     float **out_uvs,        /* [vcount*2], UV1 */
                     float **out_uvs2,       /* [vcount*2], UV2 (lightmap), 可为 NULL */
                     int32_t **out_indices,  /* [icount] */
                     uint32_t *out_vcount,
                     uint32_t *out_icount)
{
    if (size < 0x44 + 12) return -1;

    /* 读取 header */
    uint32_t version = *(const uint32_t*)(data + 0x00);
    uint32_t flag    = *(const uint32_t*)(data + 0x04);
    uint32_t vbytes  = *(const uint32_t*)(data + 0x08);
    uint32_t vcount  = *(const uint32_t*)(data + 0x0C);
    uint32_t fcount  = *(const uint32_t*)(data + 0x10);

    /* 基本校验 */
    if (version > 200) return -1;
    if (vbytes < 20 || vbytes > 48) return -1;
    if (vcount < 1 || vcount > 500000) return -1;
    if (fcount < 3 || fcount > 1000000) return -1;

    /* 校验文件大小 */
    size_t expected = 0x44 + (size_t)vcount * vbytes + (size_t)fcount * 2;
    if (size < expected) return -1;

    /* 解析顶点位置和 UV */
    *out_vcount = vcount;
    *out_positions = (float*)malloc(vcount * 3 * sizeof(float));
    *out_uvs       = (float*)malloc(vcount * 2 * sizeof(float));

    int uv_off = get_uv_offset(vbytes, flag);
    int uv2_off;
    uv2_format_t uv2_fmt;
    get_uv2_info(vbytes, flag, &uv2_off, &uv2_fmt);
    int has_uv2 = (uv2_fmt != UV2_NONE);

    const uint8_t *vert_base = data + 0x44;

    for (uint32_t i = 0; i < vcount; i++) {
        const uint8_t *v = vert_base + (size_t)i * vbytes;

        /* Position: 3 floats (12 bytes) at offset 0 */
        float px, py, pz;
        memcpy(&px, v + 0,  4);
        memcpy(&py, v + 4,  4);
        memcpy(&pz, v + 8,  4);
        (*out_positions)[i*3 + 0] = px;
        (*out_positions)[i*3 + 1] = py;
        (*out_positions)[i*3 + 2] = -pz;  /* 修复前向轴：MSH -Z→+Z 适配 Maya */

        /* UV1: 2 floats (8 bytes) at uv_off */
        if (uv_off >= 0) {
            float u, vv;
            memcpy(&u,  v + uv_off + 0, 4);
            memcpy(&vv, v + uv_off + 4, 4);
            (*out_uvs)[i*2 + 0] = u;
            (*out_uvs)[i*2 + 1] = 1.0f - vv;   /* V 翻转（与 Python 版一致） */
        } else {
            (*out_uvs)[i*2 + 0] = 0.0f;
            (*out_uvs)[i*2 + 1] = 0.0f;
        }

        /* UV2 (lightmap) */
        if (out_uvs2 && has_uv2) {
            if (uv2_fmt == UV2_FLOAT2) {
                float u2, v2;
                memcpy(&u2, v + uv2_off + 0, 4);
                memcpy(&v2, v + uv2_off + 4, 4);
                (*out_uvs2)[i*2 + 0] = u2;
                (*out_uvs2)[i*2 + 1] = 1.0f - v2;
            } else if (uv2_fmt == UV2_UINT16_UNORM) {
                uint16_t u2_raw, v2_raw;
                memcpy(&u2_raw, v + uv2_off + 0, 2);
                memcpy(&v2_raw, v + uv2_off + 2, 2);
                (*out_uvs2)[i*2 + 0] = u2_raw / 32767.0f;
                (*out_uvs2)[i*2 + 1] = 1.0f - (v2_raw / 32767.0f);
            }
        }
    }

    /* 解析索引（uint16, 小端序三角形列表） */
    *out_icount = fcount;
    *out_indices = (int32_t*)malloc(fcount * sizeof(int32_t));
    const uint8_t *idx_base = vert_base + (size_t)vcount * vbytes;
    for (uint32_t i = 0; i < fcount; i++) {
        uint16_t idx;
        memcpy(&idx, idx_base + i * 2, 2);
        (*out_indices)[i] = (int32_t)idx;
    }

    return 0;
}

/* =========================================================================
 * FBX 导出
 * ========================================================================= */

static int export_fbx(const char *input_path, const char *output_path)
{
    /* 读取 MSH 文件 */
    FILE *fp = fopen(input_path, "rb");
    if (!fp) {
        fprintf(stderr, "ERROR: Cannot open input file: %s\n", input_path);
        return 1;
    }
    fseek(fp, 0, SEEK_END);
    size_t file_size = (size_t)ftell(fp);
    fseek(fp, 0, SEEK_SET);

    uint8_t *raw_data = (uint8_t*)malloc(file_size);
    if (!raw_data || fread(raw_data, 1, file_size, fp) != file_size) {
        fprintf(stderr, "ERROR: Failed to read: %s\n", input_path);
        fclose(fp);
        free(raw_data);
        return 1;
    }
    fclose(fp);

    /* 解析 MSH */
    float   *positions = NULL;
    float   *uvs       = NULL;
    float   *uvs2      = NULL;
    int32_t *indices   = NULL;
    uint32_t vcount, icount;

    /* 预读 header 获取 vcount 以预分配 UV2 缓冲区 */
    {
        uint32_t tmp_vbytes = *(const uint32_t*)(raw_data + 0x08);
        uint32_t tmp_flag   = *(const uint32_t*)(raw_data + 0x04);
        uint32_t tmp_vcount = *(const uint32_t*)(raw_data + 0x0C);
        int tmp_off;
        uv2_format_t tmp_fmt;
        get_uv2_info(tmp_vbytes, tmp_flag, &tmp_off, &tmp_fmt);
        if (tmp_fmt != UV2_NONE)
            uvs2 = (float*)malloc(tmp_vcount * 2 * sizeof(float));
    }

    if (parse_msh(raw_data, file_size,
                  &positions, &uvs, &uvs2, &indices,
                  &vcount, &icount) != 0) {
        fprintf(stderr, "ERROR: Unsupported MSH format: %s\n", input_path);
        free(raw_data);
        free(uvs2);
        return 1;
    }
    free(raw_data);

    /* ── 计算顶点法线 ── */
    float *normals = (float*)malloc(vcount * 3 * sizeof(float));
    compute_vertex_normals(positions, indices, vcount, icount, normals);

    /* ── 查找并解析 MDF 材质 ── */
    char mdf_path[MAX_PATH * 2] = "";
    char material_name[256] = "";
    int has_mdf = find_mdf_for_msh(input_path, mdf_path, sizeof(mdf_path));
    if (has_mdf) {
        if (!parse_mdf_material_name(mdf_path, material_name, sizeof(material_name))) {
            has_mdf = 0;
        }
    }

    /* 提取模型名 */
    const char *fname = strrchr(input_path, PATH_SEP);
    fname = fname ? fname + 1 : input_path;
    char model_name[512];
    {
        size_t len = strlen(fname);
        const char *dot = strstr(fname, ".mdl-msh");
        if (dot) {
            size_t base_len = (size_t)(dot - fname);
            const char *num_part = dot + 8;
            size_t num_len = len - (size_t)(num_part - fname);
            if (base_len + num_len < sizeof(model_name)) {
                memcpy(model_name, fname, base_len);
                memcpy(model_name + base_len, num_part, num_len);
                model_name[base_len + num_len] = '\0';
            } else {
                snprintf(model_name, sizeof(model_name), "%s", fname);
            }
        } else {
            snprintf(model_name, sizeof(model_name), "%s", fname);
        }
    }

    /* ── 构建 FBX ── */
    ufbxw_scene *scene = ufbxw_create_scene(NULL);

    /* 节点 */
    ufbxw_node node = ufbxw_create_node(scene);
    ufbxw_set_name(scene, node.id, model_name);

    /* 网格 */
    ufbxw_mesh mesh = ufbxw_create_mesh(scene);
    ufbxw_set_name(scene, mesh.id, model_name);
    ufbxw_node_set_attribute(scene, node, mesh.id);

    /* ── 材质 (从 MDF) ── */
    ufbxw_material mat = ufbxw_null_material;
    if (has_mdf) {
        mat = ufbxw_create_material(scene, UFBXW_MATERIAL_FBX_LAMBERT);
        ufbxw_set_name(scene, mat.id, material_name);
        /* 链接材质到节点 */
        ufbxw_node_set_material(scene, node, 0, mat);
        ufbxw_mesh_set_single_material(scene, mesh, 0);
    }

    /* ── 顶点位置 ── */
    {
        ufbxw_vec3 *fbx_positions = (ufbxw_vec3*)malloc(vcount * sizeof(ufbxw_vec3));
        for (uint32_t i = 0; i < vcount; i++) {
            fbx_positions[i].x = (ufbxw_real)positions[i*3+0];
            fbx_positions[i].y = (ufbxw_real)positions[i*3+1];
            fbx_positions[i].z = (ufbxw_real)positions[i*3+2];
        }
        ufbxw_vec3_buffer pos_buf = ufbxw_view_vec3_array(scene, fbx_positions, vcount);
        ufbxw_mesh_set_vertices(scene, mesh, pos_buf);
        free(fbx_positions);
    }

    /* ── 法线 ── */
    {
        ufbxw_vec3 *fbx_normals = (ufbxw_vec3*)malloc(vcount * sizeof(ufbxw_vec3));
        for (uint32_t i = 0; i < vcount; i++) {
            fbx_normals[i].x = (ufbxw_real)normals[i*3+0];
            fbx_normals[i].y = (ufbxw_real)normals[i*3+1];
            fbx_normals[i].z = (ufbxw_real)normals[i*3+2];
        }
        ufbxw_vec3_buffer nrm_buf = ufbxw_view_vec3_array(scene, fbx_normals, vcount);
        ufbxw_mesh_set_normals(scene, mesh, nrm_buf, UFBXW_ATTRIBUTE_MAPPING_VERTEX);
        free(fbx_normals);
    }

    /* UV1 → ufbxw_vec2 buffer, ByPolygonVertex (Blender 4.2 兼容) */
    {
        /* 展开到 per-polygon-vertex: 每个三角形顶点一个 UV */
        ufbxw_vec2 *fbx_uvs = (ufbxw_vec2*)malloc(icount * sizeof(ufbxw_vec2));
        for (uint32_t i = 0; i < icount; i++) {
            uint32_t vi = indices[i];
            if (vi < vcount) {
                fbx_uvs[i].x = (ufbxw_real)uvs[vi*2+0];
                fbx_uvs[i].y = (ufbxw_real)uvs[vi*2+1];
            } else {
                fbx_uvs[i].x = 0.0f;
                fbx_uvs[i].y = 0.0f;
            }
        }
        ufbxw_vec2_buffer uv_buf = ufbxw_view_vec2_array(scene, fbx_uvs, icount);
        ufbxw_mesh_set_uvs(scene, mesh, 0, uv_buf, UFBXW_ATTRIBUTE_MAPPING_POLYGON_VERTEX);
        free(fbx_uvs);
    }

    /* UV2 (lightmap), ByPolygonVertex */
    if (uvs2) {
        ufbxw_vec2 *fbx_uvs2 = (ufbxw_vec2*)malloc(icount * sizeof(ufbxw_vec2));
        for (uint32_t i = 0; i < icount; i++) {
            uint32_t vi = indices[i];
            if (vi < vcount) {
                fbx_uvs2[i].x = (ufbxw_real)uvs2[vi*2+0];
                fbx_uvs2[i].y = (ufbxw_real)uvs2[vi*2+1];
            } else {
                fbx_uvs2[i].x = 0.0f;
                fbx_uvs2[i].y = 0.0f;
            }
        }
        ufbxw_vec2_buffer uv2_buf = ufbxw_view_vec2_array(scene, fbx_uvs2, icount);
        ufbxw_mesh_set_uvs(scene, mesh, 1, uv2_buf, UFBXW_ATTRIBUTE_MAPPING_POLYGON_VERTEX);
        free(fbx_uvs2);
    }

    /* 三角形索引 */
    {
        ufbxw_int_buffer idx_buf = ufbxw_view_int_array(scene, indices, icount);
        ufbxw_mesh_set_triangles(scene, mesh, idx_buf);
    }

    /* 准备场景 */
    ufbxw_prepare_scene(scene, &ufbxw_default_prepare_opts);

    /* 保存 */
    ufbxw_save_opts save_opts = { 0 };
    save_opts.format = UFBXW_SAVE_FORMAT_BINARY;
    save_opts.version = 7400;

    ufbxw_error save_error;
    bool ok = ufbxw_save_file(scene, output_path, &save_opts, &save_error);

    if (!ok) {
        fprintf(stderr, "ERROR: FBX save failed: %.*s\n",
                (int)save_error.description_length, save_error.description);
    }

    ufbxw_free_scene(scene);
    free(positions);
    free(uvs);
    free(uvs2);
    free(indices);
    free(normals);

    return ok ? 0 : 1;
}

/* =========================================================================
 * 批量导出
 * ========================================================================= */

#ifdef _WIN32

/* Windows 递归目录遍历 */
static int process_directory(const char *input_dir, const char *output_dir,
                             int *total, int *success, int *failed)
{
    WIN32_FIND_DATAW fd;
    HANDLE hFind;
    wchar_t wsearch[MAX_PATH * 2];
    wchar_t win_dir[MAX_PATH];
    wchar_t wout_dir[MAX_PATH];

    MultiByteToWideChar(CP_UTF8, 0, input_dir, -1, win_dir, MAX_PATH);
    MultiByteToWideChar(CP_UTF8, 0, output_dir, -1, wout_dir, MAX_PATH);

    _snwprintf(wsearch, MAX_PATH * 2, L"%ls\\*", win_dir);
    hFind = FindFirstFileW(wsearch, &fd);
    if (hFind == INVALID_HANDLE_VALUE) return 0;

    do {
        if (fd.cFileName[0] == L'.') continue;

        wchar_t wfull[MAX_PATH * 2];
        _snwprintf(wfull, MAX_PATH * 2, L"%ls\\%ls", win_dir, fd.cFileName);

        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            /* 递归进入子目录 */
            char sub_input[MAX_PATH], sub_output[MAX_PATH];
            WideCharToMultiByte(CP_UTF8, 0, wfull, -1, sub_input, MAX_PATH, NULL, NULL);
            snprintf(sub_output, MAX_PATH, "%s\\%S", output_dir, fd.cFileName);

            /* 创建输出子目录 */
            wchar_t wsub_out[MAX_PATH];
            MultiByteToWideChar(CP_UTF8, 0, sub_output, -1, wsub_out, MAX_PATH);
            CreateDirectoryW(wsub_out, NULL);

            process_directory(sub_input, sub_output, total, success, failed);
        } else {
            /* 检查是否匹配 *.mdl-msh* */
            char fname_utf8[MAX_PATH];
            WideCharToMultiByte(CP_UTF8, 0, fd.cFileName, -1, fname_utf8, MAX_PATH, NULL, NULL);

            if (strstr(fname_utf8, ".mdl-msh")) {
                (*total)++;

                char input_path[MAX_PATH * 2], output_path[MAX_PATH * 2];
                snprintf(input_path, sizeof(input_path), "%s\\%s", input_dir, fname_utf8);

                /* 命名规则：移除 .mdl-msh 部分，保留编号 */
                char out_name[MAX_PATH];
                {
                    const char *dot = strstr(fname_utf8, ".mdl-msh");
                    if (dot) {
                        size_t base_len = (size_t)(dot - fname_utf8);
                        const char *num_part = dot + 8;
                        snprintf(out_name, sizeof(out_name), "%.*s%s.fbx",
                                 (int)base_len, fname_utf8, num_part);
                    } else {
                        snprintf(out_name, sizeof(out_name), "%s.fbx", fname_utf8);
                    }
                }
                snprintf(output_path, sizeof(output_path), "%s\\%s", output_dir, out_name);

                /* 始终覆盖已存在的输出文件 */
                int ret = export_fbx(input_path, output_path);
                if (ret == 0) {
                    (*success)++;
                } else {
                    (*failed)++;
                }

                /* 每 100 个文件打印进度 */
                if ((*total) % 100 == 0) {
                    fprintf(stderr, "  Progress: %d total, %d ok, %d failed\n",
                            *total, *success, *failed);
                }
            }
        }
    } while (FindNextFileW(hFind, &fd));

    FindClose(hFind);
    return 0;
}

#else

#include <dirent.h>
#include <sys/stat.h>

static int process_directory(const char *input_dir, const char *output_dir,
                             int *total, int *success, int *failed)
{
    DIR *dir = opendir(input_dir);
    if (!dir) return 0;

    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_name[0] == '.') continue;

        char full_path[MAX_PATH * 2];
        snprintf(full_path, sizeof(full_path), "%s/%s", input_dir, entry->d_name);

        struct stat st;
        if (stat(full_path, &st) != 0) continue;

        if (S_ISDIR(st.st_mode)) {
            char sub_out[MAX_PATH];
            snprintf(sub_out, sizeof(sub_out), "%s/%s", output_dir, entry->d_name);
            mkdir(sub_out, 0755);
            process_directory(full_path, sub_out, total, success, failed);
        } else if (strstr(entry->d_name, ".mdl-msh")) {
            (*total)++;
            char out_path[MAX_PATH * 2];
            const char *dot = strstr(entry->d_name, ".mdl-msh");
            if (dot) {
                size_t base_len = (size_t)(dot - entry->d_name);
                const char *num_part = dot + 8;
                snprintf(out_path, sizeof(out_path), "%s/%.*s%s.fbx",
                         output_dir, (int)base_len, entry->d_name, num_part);
            } else {
                snprintf(out_path, sizeof(out_path), "%s/%s.fbx",
                         output_dir, entry->d_name);
            }
            int ret = export_fbx(full_path, out_path);
            if (ret == 0) (*success)++;
            else (*failed)++;
        }
    }
    closedir(dir);
    return 0;
}

#endif

/* =========================================================================
 * 主入口
 * ========================================================================= */

static void print_usage(const char *prog)
{
    fprintf(stderr,
        "msh2fbx — Star Conflict .mdl-mshXXX → FBX converter\n"
        "\n"
        "Usage:\n"
        "  %s <input.msh>                 Convert single file → input.fbx\n"
        "  %s <input.msh> <output.fbx>    Convert single file\n"
        "  %s --batch <dir> <outdir>      Batch convert directory tree\n"
        "\n"
        "Options:\n"
        "  --help, -h      Show this help\n"
        "\n"
        "Supported: .mdl-msh000 ~ .mdl-msh1308 (VBytes 20/24/28/32/36/40)\n"
        "Naming:   plasma_gun_mod1.mdl-msh000 → plasma_gun_mod1000.fbx\n",
        prog, prog, prog);
}

int main(int argc, char *argv[])
{
    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }

    /* 帮助 */
    if (strcmp(argv[1], "--help") == 0 || strcmp(argv[1], "-h") == 0) {
        print_usage(argv[0]);
        return 0;
    }

    /* 批量模式 */
    if (strcmp(argv[1], "--batch") == 0) {
        if (argc < 4) {
            fprintf(stderr, "ERROR: --batch requires <input_dir> <output_dir>\n");
            return 1;
        }
        const char *input_dir  = argv[2];
        const char *output_dir = argv[3];

        fprintf(stderr, "Batch mode: %s → %s\n", input_dir, output_dir);
        fprintf(stderr, "Scanning...\n");

        int total = 0, success = 0, failed = 0;
        process_directory(input_dir, output_dir, &total, &success, &failed);

        fprintf(stderr, "\nDone. Total: %d, OK: %d, Failed: %d\n",
                total, success, failed);
        return (failed > 0) ? 1 : 0;
    }

    /* 单文件模式 */
    const char *input_path  = argv[1];
    const char *output_path;

    if (argc >= 3) {
        output_path = argv[2];
    } else {
        /* 自动生成输出路径 */
        static char auto_out[MAX_PATH * 2];
        snprintf(auto_out, sizeof(auto_out), "%s.fbx", input_path);
        output_path = auto_out;
    }

    return export_fbx(input_path, output_path);
}
