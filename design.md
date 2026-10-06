# Design Specification: Checksheet Control Center

> **Design Read**: Manufacturing Quality Checksheet Control Center for QC operators, supervisors, and management in a modern B2B SaaS engineering style (Linear / Vercel / Supabase aesthetic), dial **ENERGY 2 / RHYTHM 2 / MOTION 1**.
> **Compliance**: Strict compliance with `/antislop` and `/antislop-ui` guidelines (no generic AI slop, no decorative mesh or rainbow gradients, purposeful color hierarchy, WCAG AA contrast, zero em dashes).

---

## 1. Executive Summary & Aesthetic Direction

The system transforms from an ad-hoc internal utility into a precision engineering B2B SaaS control tower.
Key visual inspirations:
- **Linear**: Ultra-crisp typography, monospace data tokens, restrained border-defined surfaces, and keyboard-centric ergonomics.
- **Supabase / Vercel**: Rich dark zinc canvas (`#09090b`), subtle card surface elevations (`#121215` / `#18181b`), crisp hairline borders (`#27272a`), and targeted semantic accents.

---

## 2. Dashboard Architecture ("Selamat Bertugas" Page 1)

### 2.1 Problem in Previous Dashboard
1. The welcome greeting ("Selamat bertugas") gave generic total counts without category context.
2. Category was completely missing from the Dashboard, forcing users to click blindly into the Checksheets page to discover where workloads actually lay.
3. The recent checksheets table omitted the Category column, making it impossible to distinguish between raw coil Material, Subcont stamping, and Accuracy items.

### 2.2 Modern SaaS Dashboard Structure
1. **Command Hero Banner**:
   - Operator identity tag with role chip (`ADMIN QC` / `OPERATOR QC`).
   - Clean, confident typography with live time/session indicator.
   - Live breakdown summary badge showing all active categories at a glance.
   - Quick action buttons (Buka Workspace, Master Part, Audit).

2. **Categorical Health & Distribution Grid (New Core Widget)**:
   - Prominently displays the 5 official QC categories:
     * **Incomming Subcont Part**: Amber theme, supplier stamping parts.
     * **Incomming Material**: Emerald theme, IQC raw material & coil sheets.
     * **Incomming Std Part**: Sky theme, purchased standard fasteners & brackets.
     * **Accuracy SSW**: Indigo theme, SSW stamping accuracy inspections.
     * **Accuracy**: Violet theme, core quality accuracy master checks.
   - Each category card displays:
     * Total part count and percentage of total catalog.
     * Micro progress bar showing completion rate (`Done` vs `Pending`).
     * Direct click navigation: clicking any category card immediately opens the Workspace filtered to that exact category.

3. **KPI Metrics Strip (Workflow Health)**:
   - 7 precision telemetry tiles: `Total Checksheet`, `Checksheet Done`, `Siap Kirim`, `Belum Dikerjakan`, `Perlu Revisi Isi`, `Perlu Revisi Gambar`, `Tidak Ada Part`.
   - Polished SaaS styling: subtle colored status indicator pill, mono metric count, and contextual micro-subtitle.

4. **Split Intelligence Section (2 Columns)**:
   - **Left**: *Progres per Customer* (MMKI, HPM, SIM / TTMIN) with multi-stage progress bars.
   - **Right**: *Distribusi Penugasan Tim* (Zul, Iqbal, Rama, Yogi, Unassigned) with direct batch dispatch buttons.

5. **Live Action Table (Checksheet Siap Dikerjakan)**:
   - Includes dedicated **Kategori** column with clean, low-saturation tag badges.
   - Monospace part numbers with copy capability.
   - Customer and Model hierarchy.
   - Contextual action buttons (`Review & Edit` / `Buka Studio`).

---

## 3. Checksheets Operational Workspace (Page 2)

### 3.1 Two-Tier Hierarchical Control Bar
1. **Tier 1 (Workflow Tabs)**:
   - `Perlu Dikerjakan` (To-Do aggregate of Belum Dikerjakan + Revisi).
   - `Siap Kirim` (Reviewed & approved for FactoryHub automation).
   - `Checksheet Done` (Completed and active on FactoryHub).
   - `Semua Part` (Full archive).
   - `Masalah / Belum Terdaftar` (Exception handling).
2. **Tier 2 (Category Filter Bar)**:
   - Large segmented chips: `Semua Kategori`, `Subcont Part`, `Material`, `Std Part`, `Accuracy SSW`, `Accuracy`.
   - Distinct color dots and dynamic counts.

### 3.2 Row Presentation
- Clean tabular rows with hairline dividers.
- Drawing thumbnail previews with lightbox zoom.
- FactoryHub synchronization link status with direct deep links.

---

## 4. Design System Tokens & Antislop Principles

### 4.1 Surface & Border Palette
- **Canvas Ground**: `zinc-950` (`#09090b`)
- **Card Surface**: `zinc-900/90` (`#18181b`)
- **Elevated Hover Surface**: `zinc-800/80` (`#27272a`)
- **Borders & Dividers**: `zinc-800` (`#27272a`) with subtle `zinc-700` (`#3f3f46`) on interactive elements.

### 4.2 Semantic Category Accents
- `Incomming Subcont Part`: Amber (`amber-400` / `amber-950` bg / `amber-800` border)
- `Incomming Material`: Emerald (`emerald-400` / `emerald-950` bg / `emerald-800` border)
- `Incomming Std Part`: Sky (`sky-400` / `sky-950` bg / `sky-800` border)
- `Accuracy SSW`: Indigo (`indigo-400` / `indigo-950` bg / `indigo-800` border)
- `Accuracy`: Violet (`violet-400` / `violet-950` bg / `violet-800` border)

### 4.3 Typography & Motion
- Font Families: Inter / Outfit for display, JetBrains Mono / SF Mono for part numbers and numerical metrics.
- Transitions: Snappy 150ms-200ms ease-out transitions. No bouncy decorative keyframes.
- Strict Copywriting Rule: Zero em dashes (`—`) in all UI labels and notifications.
