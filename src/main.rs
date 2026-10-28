#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use eframe::egui;
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, HashMap, HashSet},
    env, fs,
    path::{Path, PathBuf},
};

const DEFAULT_CATALOG: &str = include_str!("../proveedores.json");

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Provider {
    #[serde(default)]
    id: String,
    name: String,
    #[serde(default)]
    domain: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    logo_url: String,
}

impl Provider {
    fn new(name: &str) -> Self {
        Self { id: provider_key(name), name: name.to_owned(), domain: String::new(), logo_url: String::new() }
    }
}

#[derive(Deserialize)]
#[serde(untagged)]
enum CatalogEntry {
    Name(String),
    Record(Provider),
}

#[derive(Default, Serialize, Deserialize)]
struct SavedChecks {
    #[serde(default)]
    checks: BTreeMap<String, bool>,
}

#[derive(Deserialize)]
struct LegacyState {
    providers: Vec<LegacyProvider>,
}

#[derive(Deserialize)]
struct LegacyProvider {
    name: String,
    owned: bool,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Filter { All, Owned, Missing }

struct CatalogApp {
    providers: Vec<Provider>,
    checks: BTreeMap<String, bool>,
    icons: HashMap<String, egui::TextureHandle>,
    missing_icons: HashSet<String>,
    catalog_file: PathBuf,
    logos_dir: PathBuf,
    state_file: PathBuf,
    search: String,
    new_provider: String,
    filter: Filter,
    status: String,
}

fn provider_key(name: &str) -> String {
    let normalized: String = name.chars()
        .flat_map(char::to_lowercase)
        .filter(|c| c.is_alphanumeric())
        .collect();
    // Conserva las casillas anteriores al corregir nombres comerciales.
    match normalized.as_str() {
        "pragmaticplay" => "pragmatic".into(),
        "playngo" => "playandgo".into(),
        "3oaksgaming" => "3oaks".into(),
        "relaxgaming" => "relagaming".into(),
        "spinomenal" => "spinometal".into(),
        "belatragames" => "belatra".into(),
        "nolimitcity" => "nolimit".into(),
        "hacksawgaming" => "hacksaw".into(),
        "evolution" => "evolutiongaming".into(),
        "plati liveplatipus" | "platiliveplatipus" => "platiplus".into(),
        "yggdrasilgaming" => "yggdrasil".into(),
        _ => normalized,
    }
}

fn normalize(providers: Vec<Provider>) -> Vec<Provider> {
    let mut seen = HashSet::new();
    let mut result = Vec::new();
    for mut provider in providers {
        provider.name = provider.name.trim().to_owned();
        provider.domain = provider.domain.trim().to_lowercase();
        provider.logo_url = provider.logo_url.trim().to_owned();
        let id = if provider.id.trim().is_empty() { provider_key(&provider.name) }
                 else { provider_key(provider.id.trim()) };
        if !provider.name.is_empty() && !id.is_empty() && seen.insert(id.clone()) {
            provider.id = id;
            result.push(provider);
        }
    }
    result.sort_by_key(|p| p.name.to_lowercase());
    result
}

fn catalog_path() -> PathBuf {
    let near_exe = env::current_exe().ok()
        .and_then(|p| p.parent().map(|dir| dir.join("proveedores.json")));
    let from_cwd = env::current_dir().ok().map(|dir| dir.join("proveedores.json"));
    if let Some(path) = near_exe.as_ref().filter(|p| p.is_file()) { return path.clone(); }
    if let Some(path) = from_cwd.as_ref().filter(|p| p.is_file()) { return path.clone(); }
    near_exe.or(from_cwd).unwrap_or_else(|| PathBuf::from("proveedores.json"))
}

fn local_state_dir() -> PathBuf {
    if let Some(path) = env::var_os("APPDATA") {
        return PathBuf::from(path).join("ProveedoresChecklist");
    }
    if let Some(path) = env::var_os("XDG_CONFIG_HOME") {
        return PathBuf::from(path).join("catalogo-proveedores");
    }
    if let Some(path) = env::var_os("HOME") {
        return PathBuf::from(path).join(".config").join("catalogo-proveedores");
    }
    PathBuf::from(".").join("catalogo-proveedores")
}

fn parse_catalog(text: &str) -> Result<Vec<Provider>, String> {
    let entries: Vec<CatalogEntry> = serde_json::from_str(text)
        .map_err(|e| format!("Catálogo JSON inválido: {e}"))?;
    let providers = entries.into_iter().map(|item| match item {
        CatalogEntry::Name(name) => Provider::new(&name),
        CatalogEntry::Record(provider) => provider,
    }).collect();
    Ok(normalize(providers))
}

fn read_catalog(path: &Path) -> Result<Vec<Provider>, String> {
    match fs::read_to_string(path) {
        Ok(s) => parse_catalog(&s),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => parse_catalog(DEFAULT_CATALOG),
        Err(e) => Err(format!("No se pudo leer {}: {e}", path.display())),
    }
}

fn write_catalog(path: &Path, providers: &[Provider]) -> Result<(), String> {
    if let Some(folder) = path.parent() { fs::create_dir_all(folder).map_err(|e| e.to_string())?; }
    let body = serde_json::to_string_pretty(providers).map_err(|e| e.to_string())? + "\n";
    fs::write(path, body).map_err(|e| e.to_string())
}

fn load_checks(path: &Path) -> Result<BTreeMap<String, bool>, String> {
    match fs::read_to_string(path) {
        Ok(s) => {
            let saved: SavedChecks = serde_json::from_str(&s)
                .map_err(|e| format!("Error al recuperar marcas: {e}"))?;
            Ok(saved.checks)
        }
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            // Importa el formato usado por la primera versión.
            let old = path.with_file_name("proveedores.json");
            match fs::read_to_string(old) {
                Ok(s) => {
                    let previous: LegacyState = serde_json::from_str(&s)
                        .map_err(|e| format!("Estado anterior inválido: {e}"))?;
                    let mut saved = BTreeMap::new();
                    for item in previous.providers {
                        let selected = saved.entry(provider_key(&item.name)).or_insert(false);
                        *selected |= item.owned;
                    }
                    Ok(saved)
                }
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(BTreeMap::new()),
                Err(e) => Err(format!("No se pudo leer estado anterior: {e}")),
            }
        }
        Err(e) => Err(format!("No se pudo leer marcas guardadas: {e}")),
    }
}

fn persist_checks(path: &Path, checks: &BTreeMap<String, bool>) -> Result<(), String> {
    if let Some(folder) = path.parent() { fs::create_dir_all(folder).map_err(|e| e.to_string())?; }
    let content = serde_json::to_string_pretty(&SavedChecks { checks: checks.clone() })
        .map_err(|e| e.to_string())?;
    fs::write(path, content + "\n").map_err(|e| e.to_string())
}

fn csv_cell(value: &str) -> String {
    let dangerous = matches!(value.trim_start().chars().next(), Some('=' | '+' | '-' | '@'));
    let cleaned = if dangerous { format!("'{value}") } else { value.to_owned() };
    format!("\"{}\"", cleaned.replace('"', "\"\""))
}

fn export_csv(path: &Path, providers: &[Provider], checks: &BTreeMap<String, bool>) -> Result<(), String> {
    let mut content = String::from("\u{FEFF}Proveedor;Estado;Sitio\r\n");
    for p in providers {
        content.push_str(&format!("{};{};{}\r\n",
            csv_cell(&p.name),
            if checks.get(&p.id).copied().unwrap_or(false) { "Tengo" } else { "Me falta" },
            csv_cell(&p.domain),
        ));
    }
    fs::write(path, content).map_err(|e| e.to_string())
}

fn initials(name: &str) -> String {
    name.split_whitespace().take(2).filter_map(|part| part.chars().next())
        .collect::<String>().to_uppercase()
}

impl CatalogApp {
    fn new() -> Self {
        let catalog_file = catalog_path();
        let logos_dir = catalog_file.parent().unwrap_or(Path::new(".")).join("logos");
        let state_file = local_state_dir().join("estado.json");
        let (providers, catalog_status) = match read_catalog(&catalog_file) {
            Ok(p) => (p, String::new()),
            Err(e) => (parse_catalog(DEFAULT_CATALOG).expect("JSON integrado válido"), e),
        };
        let (checks, state_status) = match load_checks(&state_file) {
            Ok(c) => (c, String::new()),
            Err(e) => (BTreeMap::new(), e),
        };
        let status = if !catalog_status.is_empty() { format!("ERROR catálogo externo: {catalog_status}") }
                     else if !state_status.is_empty() { format!("ERROR marcas: {state_status}") }
                     else { "Catálogo cargado. Las casillas se guardan automáticamente.".into() };
        Self {
            providers, checks, catalog_file, logos_dir, state_file, status,
            icons: HashMap::new(), missing_icons: HashSet::new(),
            search: String::new(), new_provider: String::new(), filter: Filter::All,
        }
    }

    fn load_icons(&mut self, ctx: &egui::Context) {
        for provider in &self.providers {
            if self.icons.contains_key(&provider.id) || self.missing_icons.contains(&provider.id) {
                continue;
            }
            let path = self.logos_dir.join(format!("{}.png", provider.id));
            let icon = fs::read(&path).ok()
                .and_then(|content| image::load_from_memory(&content).ok())
                .map(|image| {
                    let rgba = image.to_rgba8();
                    let dimensions = [rgba.width() as usize, rgba.height() as usize];
                    let data = egui::ColorImage::from_rgba_unmultiplied(dimensions, rgba.as_raw());
                    ctx.load_texture(format!("proveedor-{}", provider.id), data, egui::TextureOptions::LINEAR)
                });
            match icon {
                Some(icon) => { self.icons.insert(provider.id.clone(), icon); }
                None => { self.missing_icons.insert(provider.id.clone()); }
            }
        }
    }

    fn save_checks(&mut self) {
        self.status = match persist_checks(&self.state_file, &self.checks) {
            Ok(()) => "Marcas guardadas.".into(),
            Err(e) => format!("ERROR al guardar marcas: {e}"),
        };
    }

    fn update_catalog(&mut self, providers: Vec<Provider>) {
        let providers = normalize(providers);
        self.status = match write_catalog(&self.catalog_file, &providers) {
            Ok(()) => {
                self.providers = providers;
                format!("Catálogo actualizado: {} proveedores.", self.providers.len())
            },
            Err(e) => format!("ERROR al guardar lista: {e}"),
        };
    }

    fn add_provider(&mut self) {
        let name = self.new_provider.trim().to_owned();
        if name.is_empty() { return; }
        let provider = Provider::new(&name);
        if self.providers.iter().any(|p| p.id == provider.id) {
            self.status = format!("El proveedor {name} ya existe");
            return;
        }
        let mut next = self.providers.clone();
        next.push(provider.clone());
        self.update_catalog(next);
        if self.providers.iter().any(|p| p.id == provider.id) {
            self.new_provider.clear();
        }
    }

    fn reload(&mut self) {
        match read_catalog(&self.catalog_file) {
            Ok(providers) => {
                self.providers = providers;
                self.icons.clear();
                self.missing_icons.clear();
                self.logos_dir = self.catalog_file.parent().unwrap_or(Path::new(".")).join("logos");
                self.status = format!("Catálogo recargado ({}). Se conservaron las marcas.", self.providers.len());
            }
            Err(e) => self.status = format!("ERROR al recargar: {e}"),
        }
    }
}

impl eframe::App for CatalogApp {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        self.load_icons(ui.ctx());
        let mut checks_changed = false;
        egui::CentralPanel::default().show(ui, |ui| {
            ui.heading("Catálogo de proveedores");
            ui.label("Miniatura, nombre comercial y disponibilidad.");
            ui.add_space(8.0);

            let total = self.providers.len();
            let owned = self.providers.iter()
                .filter(|p| self.checks.get(&p.id).copied().unwrap_or(false)).count();
            ui.horizontal_wrapped(|ui| {
                ui.strong(format!("TOTAL: {total}"));
                ui.separator();
                ui.strong(format!("TENGO: {owned}"));
                ui.separator();
                ui.strong(format!("ME FALTAN: {}", total - owned));
            });
            let progress = if total == 0 { 0.0 } else { owned as f32 / total as f32 };
            ui.add(egui::ProgressBar::new(progress).show_percentage().desired_width(ui.available_width()));

            ui.add_space(8.0);
            ui.horizontal(|ui| {
                ui.label("Buscar:");
                ui.add(egui::TextEdit::singleline(&mut self.search)
                    .hint_text("Proveedor").desired_width(260.0));
            });
            ui.horizontal(|ui| {
                ui.selectable_value(&mut self.filter, Filter::All, "Todos");
                ui.selectable_value(&mut self.filter, Filter::Owned, "Tengo");
                ui.selectable_value(&mut self.filter, Filter::Missing, "Me faltan");
            });
            ui.separator();

            let search = self.search.to_lowercase();
            let mut to_remove: Option<String> = None;
            egui::ScrollArea::vertical().max_height(440.0).show(ui, |ui| {
                for provider in &self.providers {
                    let id = provider.id.clone();
                    let mut owned = self.checks.get(&id).copied().unwrap_or(false);
                    if !provider.name.to_lowercase().contains(&search) { continue; }
                    if self.filter == Filter::Owned && !owned { continue; }
                    if self.filter == Filter::Missing && owned { continue; }
                    let icon = self.icons.get(&id).cloned();

                    ui.horizontal(|ui| {
                        if let Some(texture) = icon {
                            ui.image((texture.id(), egui::vec2(44.0, 44.0)));
                        } else {
                            ui.add_sized([44.0, 44.0],
                                egui::Label::new(egui::RichText::new(initials(&provider.name)).strong().size(18.0)));
                        }
                        if ui.checkbox(&mut owned, &provider.name).changed() {
                            self.checks.insert(id.clone(), owned);
                            checks_changed = true;
                        }
                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            if ui.small_button("Quitar").clicked() {
                                to_remove = Some(id.clone());
                            }
                            if !provider.domain.is_empty() {
                                ui.hyperlink_to("Web", format!("https://{}", provider.domain));
                            }
                        });
                    });
                    ui.separator();
                }
            });

            if let Some(remove_id) = to_remove {
                let next: Vec<Provider> = self.providers.iter()
                    .filter(|p| p.id != remove_id).cloned().collect();
                self.update_catalog(next);
            }

            ui.add_space(6.0);
            ui.horizontal(|ui| {
                ui.add(egui::TextEdit::singleline(&mut self.new_provider)
                    .hint_text("Agregar proveedor").desired_width(260.0));
                if ui.button("Agregar").clicked() { self.add_provider(); }
                if ui.button("Recargar catálogo").clicked() { self.reload(); }
            });
            ui.separator();
            if ui.button("Exportar CSV").clicked() {
                let path = self.state_file.with_file_name("proveedores.csv");
                self.status = match export_csv(&path, &self.providers, &self.checks) {
                    Ok(()) => format!("CSV: {}", path.display()),
                    Err(e) => format!("ERROR CSV: {e}"),
                };
            }
            ui.label(&self.status);
            ui.small(format!("Catálogo editable: {}", self.catalog_file.display()));
            ui.small(format!("Logos: {}", self.logos_dir.display()));
            ui.small(format!("Marcas privadas: {}", self.state_file.display()));
        });
        if checks_changed { self.save_checks(); }
    }
}

fn main() -> eframe::Result {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("Catálogo de proveedores")
            .with_inner_size([770.0, 850.0])
            .with_min_inner_size([550.0, 580.0]),
        ..Default::default()
    };
    eframe::run_native(
        "Catálogo de proveedores",
        options,
        Box::new(|_cc| Ok(Box::new(CatalogApp::new()))),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn catalog_has_42_unique_providers() {
        let providers = parse_catalog(DEFAULT_CATALOG).unwrap();
        assert_eq!(providers.len(), 42);
        assert_eq!(providers.iter().map(|p| &p.id).collect::<HashSet<_>>().len(), 42);
        assert!(providers.iter().all(|p| !p.domain.is_empty()));
    }

    #[test]
    fn preserves_old_check_ids() {
        assert_eq!(provider_key("Pragmatic Play"), provider_key("Pragmatic"));
        assert_eq!(provider_key("Play'n GO"), provider_key("Play and Go"));
        assert_eq!(provider_key("3 Oaks Gaming"), provider_key("3Oaks"));
        assert_eq!(provider_key("Relax Gaming"), provider_key("Rela Gaming"));
        assert_eq!(provider_key("Spinomenal"), provider_key("Spinometal"));
    }

    #[test]
    fn supports_legacy_string_catalog() {
        let old = parse_catalog(r#"["Wazdan", " wazdan ", "BGaming"]"#).unwrap();
        assert_eq!(old.len(), 2);
    }

    #[test]
    fn protects_csv_cells() {
        assert_eq!(csv_cell("=SUM(1,2)"), "\"'=SUM(1,2)\"");
        assert_eq!(csv_cell("X\"Y"), "\"X\"\"Y\"");
    }
}
