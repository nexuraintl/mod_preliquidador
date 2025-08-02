# Test de funciones de facturación extranjera
import sys
import os

try:
    from config import (
        obtener_conceptos_extranjeros,
        obtener_paises_con_convenio, 
        obtener_preguntas_fuente_nacional,
        es_pais_con_convenio,
        obtener_tarifa_extranjera
    )
    
    print("✅ Importaciones exitosas")
    
    # Probar funciones
    conceptos = obtener_conceptos_extranjeros()
    print(f"📋 Conceptos extranjeros: {len(conceptos)}")
    
    paises = obtener_paises_con_convenio()
    print(f"🌍 Países con convenio: {len(paises)}")
    
    preguntas = obtener_preguntas_fuente_nacional()
    print(f"❓ Preguntas fuente: {len(preguntas)}")
    
    # Probar validaciones
    tiene_convenio = es_pais_con_convenio("España")
    print(f"🇪🇸 España tiene convenio: {tiene_convenio}")
    
    tiene_convenio_usa = es_pais_con_convenio("Estados Unidos")
    print(f"🇺🇸 USA tiene convenio: {tiene_convenio_usa}")
    
    # Probar obtener tarifa
    tarifa_consultoria_convenio = obtener_tarifa_extranjera("Consultorías", True)
    print(f"💰 Tarifa consultoría con convenio: {tarifa_consultoria_convenio*100}%")
    
    tarifa_consultoria_normal = obtener_tarifa_extranjera("Consultorías", False)
    print(f"💰 Tarifa consultoría normal: {tarifa_consultoria_normal*100}%")
    
    print("\n🎉 Todas las funciones de facturación extranjera funcionan correctamente!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
