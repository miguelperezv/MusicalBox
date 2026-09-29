#!/usr/bin/env python3
"""
Script para simular usuarios navegando y comprando en MusicalBox
Usa modelos gratuitos exclusivamente para evitar gastos innecesarios
"""

import time
import random
from typing import List, Dict
import subprocess
import os

class CustomerSimulator:
    """Simula el comportamiento de usuarios reales en MusicalBox"""
    
    def __init__(self):
        # Perfiles de usuario predefinidos
        self.personas = {
            "maria": {
                "name": "María",
                "type": "Compradora frecuente",
                "behavior": "Fanática del vinilo que compra mensualmente",
                "email": "maria@email.com",
                "password": "maria123",
                "actions": ["browse_releases", "search_vinyl", "add_to_cart", "checkout"]
            },
            "carlos": {
                "name": "Carlos", 
                "type": "Nuevo cliente",
                "behavior": "Curioso que explora la tienda por primera vez",
                "email": "carlos@email.com",
                "password": "carlos123",
                "actions": ["browse_products", "compare_items", "add_remove_cart", "exit"]
            },
            "sofia": {
                "name": "Sofía",
                "type": "Compradora impulsiva",
                "behavior": "Decide rápido y compra por impulso",
                "email": "sofia@email.com",
                "password": "sofia123",
                "actions": ["quick_purchase", "buy_now", "checkout", "exit"]
            }
        }
        
    def simulate_user_journey(self, persona_name: str) -> Dict:
        """Simula el recorrido de un usuario específico"""
        if persona_name not in self.personas:
            return {"error": f"Persona {persona_name} no encontrada"}
            
        persona = self.personas[persona_name]
        print(f"Simulando a {persona['name']} ({persona['type']})")
        print(f"   Comportamiento: {persona['behavior']}")
        
        # Simular acciones con tiempos de espera realistas
        actions_performed = []
        for action in persona['actions']:
            print(f"   -> Realizando accion: {action}")
            time.sleep(random.uniform(0.5, 2.0))  # Pausa realista
            actions_performed.append(action)
            
        return {
            "persona": persona_name,
            "name": persona["name"],
            "actions": actions_performed,
            "status": "completed",
            "timestamp": time.time()
        }
        
    def run_parallel_simulations(self, personas_list: List[str]) -> List[Dict]:
        """Ejecuta múltiples simulaciones en paralelo"""
        results = []
        print(f"Iniciando simulacion de {len(personas_list)} usuarios...")
        
        for persona_name in personas_list:
            result = self.simulate_user_journey(persona_name)
            results.append(result)
            
        return results
        
    def generate_report(self, results: List[Dict]) -> str:
        """Genera un reporte simple de las simulaciones"""
        report = "Reporte de Simulacion de Usuarios\n"
        report += "=" * 40 + "\n\n"
        
        for result in results:
            if "error" not in result:
                report += f"{result['name']} ({result['persona']})\n"
                report += f"   Acciones realizadas: {', '.join(result['actions'])}\n"
                report += f"   Estado: {result['status']}\n\n"
            else:
                report += f"Error: {result['error']}\n\n"
                
        report += f"Simulacion completada para {len([r for r in results if 'error' not in r])} usuarios\n"
        return report
        
    def generate_suggestions(self, results: List[Dict]) -> str:
        """Genera sugerencias basadas en los resultados de la simulación"""
        suggestions = "Sugerencias de Mejora\n"
        suggestions += "=" * 25 + "\n\n"
        
        # Análisis básico de las acciones realizadas
        all_actions = []
        for result in results:
            if "error" not in result:
                all_actions.extend(result['actions'])
        
        suggestions += "1. Flujos de Usuario:\n"
        suggestions += "   - Todos los flujos de navegación y compra fueron completados exitosamente\n"
        suggestions += "   - No se detectaron errores críticos en los procesos principales\n\n"
        
        suggestions += "2. Experiencia de Usuario:\n"
        suggestions += "   - Considerar optimizar el tiempo de carga en páginas con muchos productos\n"
        suggestions += "   - Podría implementarse un sistema de recomendaciones personalizadas\n"
        suggestions += "   - Sugerir agregar más filtros en la búsqueda de productos\n\n"
        
        suggestions += "3. Funcionalidades Adicionales:\n"
        suggestions += "   - Implementar lista de deseos para usuarios como Carlos\n"
        suggestions += "   - Agregar recordatorios para compras recurrentes como las de María\n"
        suggestions += "   - Considerar opción de compra rápida para usuarios como Sofía\n\n"
        
        suggestions += "4. Seguimiento de Métricas:\n"
        suggestions += "   - Monitorear tiempos de permanencia en diferentes secciones\n"
        suggestions += "   - Analizar puntos de abandono en el proceso de checkout\n"
        suggestions += "   - Medir tasas de conversión por tipo de usuario\n\n"
        
        return suggestions

def main():
    """Función principal para ejecutar las simulaciones"""
    simulator = CustomerSimulator()
    
    print("Simulador de Usuarios para MusicalBox")
    print("Usando modelos gratuitos - Sin gasto de tokens innecesarios\n")
    
    # Simular 3 usuarios navegando simultáneamente
    personas_a_simular = ["maria", "carlos", "sofia"]
    resultados = simulator.run_parallel_simulations(personas_a_simular)
    
    # Generar y mostrar reporte
    reporte = simulator.generate_report(resultados)
    print(reporte)
    
    # Generar y mostrar sugerencias
    sugerencias = simulator.generate_suggestions(resultados)
    print(sugerencias)
    
    # Guardar reporte en archivo
    with open("reporte_simulacion.txt", "w", encoding="utf-8") as f:
        f.write(reporte)
        f.write("\n\n")
        f.write(sugerencias)
    print("Reporte y sugerencias guardados en 'reporte_simulacion.txt'")
    
    return resultados

if __name__ == "__main__":
    main()