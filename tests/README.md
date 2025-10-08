# 🧪 Tests - Preliquidador de Impuestos Colombianos

## 📋 Directorio de Pruebas

Esta carpeta contiene todos los tests del proyecto. **NO se deben crear tests en archivos de producción** (main.py, liquidadores, clasificadores, etc.).

## 🎯 Objetivo

Mantener el código de producción limpio y separado de las pruebas, siguiendo el **Principio de Separación de Responsabilidades (SRP)**.

## 📁 Estructura Sugerida

```
tests/
├── __init__.py                    # Inicializador del paquete de tests
├── README.md                      # Este archivo
├── test_liquidador.py             # Tests para liquidadores
├── test_clasificador.py           # Tests para clasificadores
├── test_config.py                 # Tests para configuración
├── test_api.py                    # Tests de endpoints API
├── test_integracion.py            # Tests de integración end-to-end
└── fixtures/                      # Datos de prueba
    ├── facturas_prueba/
    └── respuestas_esperadas/
```

## 🔧 Uso de Tests

### Ejecutar todos los tests
```bash
pytest tests/
```

### Ejecutar tests específicos
```bash
pytest tests/test_liquidador.py
pytest tests/test_liquidador.py::test_calculo_retencion
```

### Con cobertura
```bash
pytest tests/ --cov=. --cov-report=html
```

## ✅ Buenas Prácticas

1. **Separación total**: Los tests están en `tests/`, el código en módulos principales
2. **Nombres descriptivos**: `test_calculo_retencion_art383_persona_natural()`
3. **Fixtures reutilizables**: Crear datos de prueba en `fixtures/`
4. **Mocks para IA**: No hacer llamadas reales a Gemini en tests
5. **Tests aislados**: Cada test debe ser independiente

## 🚫 NO Hacer

❌ **NO** agregar tests en `main.py`
❌ **NO** agregar tests en archivos de liquidadores
❌ **NO** agregar tests en archivos de clasificadores
❌ **NO** mezclar código de producción con código de prueba

## ✅ Hacer

✅ **SÍ** crear archivos de test en `tests/`
✅ **SÍ** usar mocks para dependencias externas
✅ **SÍ** mantener tests simples y legibles
✅ **SÍ** documentar casos edge complejos
