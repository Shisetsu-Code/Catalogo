#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use eframe::egui;
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, HashSet},
    env, fs,
    path::PathBuf,
};

const DEFAULT_CATALOG: &str = include_str!("../proveedores.json");

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
enum Filter {
    All,
    Owned,
    Missing,
}

struct CatalogApp {
    providers: Vec<String>,
    checks: BTreeMap<String, bool>,
    catalog_file: PathBuf,
    state_file: PathBuf,
    search: String,
    new_provider: String,
    filter: Filter,
    status: String,
}

fn key(name: &str) -> String {
    let normalized: String = name
        .chars()
        .flat_map(char::to_lowercase)
        .filter(|c| c.is_alphanumeric())
        .collect();
    match normalized.as_str() {
        "pragmaticplay" => "pragmatic".to_string(),
        "playngo" => "playandgo".to_string(),
        "3oaksgaming" => "3oaks".to_string(),
        "belatragames" => "belatra".to_string(),
        _ => normalized,
    }
}

fn normalize(names: Vec<String>) -> Vec<String> {
    let mut seen = HashSet::new();
    let mut result = Vec::new();
    for raw in names {
        let name = raw.trim();
        let id = key(name);
        if !id.is_empty() && seen.insert(id) {
            result.push(name.to_string());
        }
    }
    result.sort_by_key(|name| name.to_lowercase());
    result
}

fn catalog_path() -> PathBuf {
    let nearby = env::current_exe()
        .ok()
        .and_then(|exe| exe.parent().map(|folder| folder.join("proveedores.json")));
    let workdir = env::current_dir().ok().map(|p| p.join("proveedores.json"));

    // Al ejecutar desde cargo, el JSON está en la raíz del repositorio.
    // Para el EXE distribuido, el JSON está junto al ejecutable.
    if let Some(path) = nearby.as_ref().filter(|p| p.is_file()) {
        return path.clone();
    }
    if let Some(path) = workdir.as_ref().filter(|p| p.is_file()) {
        return path.clone();
    }
    nearby.or(workdir).unwrap_or_else(|| PathBuf::from("proveedores.json"))
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

fn parse_catalog(text: &str) -> Result<Vec<String>, String> {
    let raw: Vec<String> = serde_json::from_str(text)
        .map_err(|e| format!("El catálogo debe ser un arreglo JSON de nombres: {e}"))?;
    Ok(normalize(raw))
}

fn read_catalog(path: &PathBuf) -> Result<Vec<String>, String> {
    match fs::read_to_string(path) {
        Ok(text) => parse_catalog(&text),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => parse_catalog(DEFAULT_CATALOG),
        Err(e) => Err(format!("No se pudo abrir {}: {e}", path.display())),
    }
}

fn save_catalog(path: &PathBuf, names: &[String]) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let serialized = serde_json::to_string_pretty(names).map_err(|e| e.to_string())? + "\n";
    fs::write(path, serialized).map_err(|e| e.to_string())
}

fn load_checks(state_file: &PathBuf) -> Result<BTreeMap<String, bool>, String> {
    match fs::read_to_string(state_file) {
        Ok(text) => {
            let loaded: SavedChecks = serde_json::from_str(&text)
                .map_err(|e| format!("Estado guardado inválido: {e}"))?;
            Ok(loaded.checks)
        }
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            // Compatible con el archivo de la versión anterior.
            let old_path = state_file.with_file_name("proveedores.json");
            match fs::read_to_string(old_path) {
                Ok(text) => {
                    let previous: LegacyState = serde_json::from_str(&text)
                        .map_err(|e| format!("No se pudo importar el estado anterior: {e}"))?;
                    let mut checks = BTreeMap::new();
                    for provider in previous.providers {
                        let entry = checks.entry(key(&provider.name)).or_insert(false);
                        *entry |= provider.owned;
                    }
                    Ok(checks)
                }
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(BTreeMap::new()),
                Err(e) => Err(format!("Error al leer estado anterior: {e}")),
            }
        }
        Err(e) => Err(format!("Error al leer estado: {e}")),
    }
}

fn persist_checks(path: &PathBuf, checks: &BTreeMap<String, bool>) -> Result<(), String> {
    if let Some(folder) = path.parent() {
        fs::create_dir_all(folder).map_err(|e| e.to_string())?;
    }
    let json = serde_json::to_string_pretty(&SavedChecks { checks: checks.clone() })
        .map_err(|e| e.to_string())?;
    fs::write(path, json + "\n").map_err(|e| e.to_string())
}

fn safe_csv_cell(value: &str) -> String {
    let dangerous = matches!(value.trim_start().chars().next(), Some('=' | '+' | '-' | '@'));
    let value = if dangerous { format!("'{value}") } else { value.to_string() };
    format!("\"{}\"", value.replace('"', "\"\""))
}

fn export_csv(path: &PathBuf, providers: &[String], checks: &BTreeMap<String, bool>) -> Result<(), String> {
    if let Some(folder) = path.parent() {
        fs::create_dir_all(folder).map_err(|e| e.to_string())?;
    }
    let mut out = String::from("\u{FEFF}Proveedor;Estado\r\n");
    for name in providers {
        let is_owned = checks.get(&key(name)).copied().unwrap_or(false);
        out.push_str(&safe_csv_cell(name));
        out.push(';');
        out.push_str(if is_owned { "Tengo" } else { "Me falta" });
        out.push_str("\r\n");
    }
    fs::write(path, out).map_err(|e| e.to_string())
}

impl CatalogApp {
    fn new() -> Self {
        let catalog_file = catalog_path();
        let state_file = local_state_dir().join("estado.json");
        let (providers, catalog_status) = match read_catalog(&catalog_file) {
            Ok(providers) => (providers, String::new()),
            Err(e) => (
                parse_catalog(DEFAULT_CATALOG).expect("El catálogo integrado debe ser válido"),
                format!("ERROR en catálogo externo (usando copia integrada): {e}"),
            ),
        };
        let (checks, check_status) = match load_checks(&state_file) {
            Ok(checks) => (checks, String::new()),
            Err(e) => (BTreeMap::new(), format!("ERROR en las marcas guardadas: {e}")),
        };
        Self {
            providers,
            checks,
            catalog_file,
            state_file,
            search: String::new(),
            new_provider: String::new(),
            filter: Filter::All,
            status: if !catalog_status.is_empty() { catalog_status } else if !check_status.is_empty() {
                check_status
            } else { "Catálogo cargado. Todos los cambios se guardan automáticamente.".to_string() },
        }
    }

    fn save_state(&mut self) {
        self.status = match persist_checks(&self.state_file, &self.checks) {
            Ok(()) => "Marcas guardadas automáticamente".to_string(),
            Err(error) => format!("ERROR al guardar marcas: {error}"),
        };
    }

    fn update_catalog(&mut self, names: Vec<String>) {
        let names = normalize(names);
        match save_catalog(&self.catalog_file, &names) {
            Ok(()) => {
                self.providers = names;
                self.status = format!("Catálogo guardado: {} proveedores", self.providers.len());
            }
            Err(error) => {
                self.status = format!("ERROR al guardar catálogo: {error}");
            }
        }
    }

    fn add_provider(&mut self) {
        let name = self.new_provider.trim();
        if name.is_empty() {
            return;
        }
        if self.providers.iter().any(|item| key(item) == key(name)) {
            self.status = format!("Ya existe el proveedor: {name}");
            return;
        }
        let mut next = self.providers.clone();
        next.push(name.to_owned());
        self.update_catalog(next);
        if self.providers.iter().any(|item| key(item) == key(name)) {
            self.new_provider.clear();
        }
    }

    fn reload_catalog(&mut self) {
        match read_catalog(&self.catalog_file) {
            Ok(providers) => {
                self.providers = providers;
                self.status = format!("Catálogo recargado: {} proveedores. Marcas conservadas.", self.providers.len());
            }
            Err(e) => self.status = format!("ERROR al recargar: {e}"),
        }
    }
}

impl eframe::App for CatalogApp {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let mut checks_changed = false;
        egui::CentralPanel::default().show(ui, |ui| {
            ui.heading("Catálogo de proveedores");
            ui.label("Marcá los proveedores que ya tenés. El catálogo se actualiza por separado.");
            ui.add_space(8.0);

            let total = self.providers.len();
            let owned = self.providers.iter()
                .filter(|name| self.checks.get(&key(name)).copied().unwrap_or(false)).count();
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
                    .hint_text("Nombre del proveedor").desired_width(260.0));
            });
            ui.horizontal(|ui| {
                ui.selectable_value(&mut self.filter, Filter::All, "Todos");
                ui.selectable_value(&mut self.filter, Filter::Owned, "Tengo");
                ui.selectable_value(&mut self.filter, Filter::Missing, "Me faltan");
            });
            ui.separator();

            let query = self.search.to_lowercase();
            let mut to_remove = None;
            egui::ScrollArea::vertical().max_height(355.0).show(ui, |ui| {
                for name in &self.providers {
                    let id = key(name);
                    let mut has_it = self.checks.get(&id).copied().unwrap_or(false);
                    if !name.to_lowercase().contains(&query) { continue; }
                    if self.filter == Filter::Owned && !has_it { continue; }
                    if self.filter == Filter::Missing && has_it { continue; }

                    ui.horizontal(|ui| {
                        if ui.checkbox(&mut has_it, name).changed() {
                            self.checks.insert(id.clone(), has_it);
                            checks_changed = true;
                        }
                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            if ui.small_button("Quitar").clicked() {
                                to_remove = Some(name.clone());
                            }
                        });
                    });
                    ui.separator();
                }
            });
            if let Some(name) = to_remove {
                let next: Vec<String> = self.providers.iter()
                    .filter(|item| key(item) != key(&name)).cloned().collect();
                self.update_catalog(next);
            }

            ui.add_space(8.0);
            ui.horizontal(|ui| {
                ui.add(egui::TextEdit::singleline(&mut self.new_provider)
                    .hint_text("Agregar proveedor").desired_width(270.0));
                if ui.button("Agregar").clicked() { self.add_provider(); }
                if ui.button("Recargar catálogo").clicked() { self.reload_catalog(); }
            });

            ui.separator();
            if ui.button("Exportar CSV").clicked() {
                let path = self.state_file.with_file_name("proveedores.csv");
                self.status = match export_csv(&path, &self.providers, &self.checks) {
                    Ok(()) => format!("CSV guardado en {}", path.display()),
                    Err(e) => format!("ERROR al exportar: {e}"),
                };
            }
            ui.label(&self.status);
            ui.small(format!("Catálogo editable: {}", self.catalog_file.display()));
            ui.small(format!("Marcas privadas: {}", self.state_file.display()));
        });
        if checks_changed { self.save_state(); }
    }
}

fn main() -> eframe::Result {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("Catálogo de proveedores")
            .with_inner_size([700.0, 770.0])
            .with_min_inner_size([530.0, 540.0]),
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
    }

    #[test]
    fn aliases_match() {
        assert_eq!(key("Pragmatic Play"), key("Pragmatic"));
        assert_eq!(key("Play'n GO"), key("Play and Go"));
        assert_eq!(key("3 Oaks Gaming"), key("3Oaks"));
    }

    #[test]
    fn deduplicates_providers() {
        let result = normalize(vec!["Wazdan".into(), " wazdan ".into(), "".into()]);
        assert_eq!(result, vec!["Wazdan"]);
    }

    #[test]
    fn protects_csv_cells() {
        assert_eq!(safe_csv_cell("=SUM(1,2)"), "\"'=SUM(1,2)\"");
        assert_eq!(safe_csv_cell("X\"Y"), "\"X\"\"Y\"");
    }
}
