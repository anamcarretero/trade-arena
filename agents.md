# Guía para agentes

## Documentación de mantenimiento

La documentación interna vive en `doc/` (singular). No confundirla con
`docs/`, que es un artefacto publicado por GitHub Pages y se regenera con el
comando `ranking`.

- Lee primero `doc/arquitectura.md` para entender módulos, contratos de datos,
  cálculo financiero, seguridad y automatizaciones.
- Consulta `doc/casos-de-uso.md` para flujos de jugadores/administración,
  publicación, privacidad y diagnóstico.
- Mantén ambas guías en español y actualízalas en el mismo cambio cuando se
  modifiquen rutas, comandos, contratos públicos, secretos, workflows,
  privacidad o reglas de rentabilidad.

## Reglas de trabajo

- Trata `players/**/*.csv.enc` como datos sensibles. Nunca descifres ni
  muestres su contenido, y nunca añadas CSV en claro al repositorio.
- No edites manualmente `docs/index.html`, `docs/ranking.md`,
  `data/public/`, `data/prices/` o `data/badges.json` salvo que el encargo sea
  precisamente una corrección de datos generados. En condiciones normales se
  producen con `python -m trader ranking`.
- Conserva la compatibilidad del formato de cifrado de `trader/secretbox.py`;
  ya existen extractos cifrados versionados que deben seguir leyéndose.
- Los importes solo pueden aparecer en salidas públicas cuando
  `show_amounts` lo autoriza. Al cambiar payloads, informes o la web, revisa
  esta frontera de privacidad explícitamente.
- Las descargas de Yahoo son tolerantes a fallos: la caché es parte de la
  reproducibilidad. No conviertas la falta de consenso de analistas en un error
  fatal del ranking.

## Verificación mínima

Ejecuta `python -m pytest tests/ -q` cuando el entorno tenga las dependencias.
Para validar el pipeline sin red ni secretos, usa:

```bash
python -m trader ranking --players-dir examples/players --prices-dir examples/prices --offline
```

Si el ejecutable local se llama `python3`, úsalo de forma equivalente. Antes
de entregar cambios, informa si no fue posible ejecutar las pruebas y por qué.
