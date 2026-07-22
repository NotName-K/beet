# Beet

Modelo de predicción y detección de apuestas de valor.

## Visión

Beet predice partidos de fútbol mediante **simulación** (no una fórmula cerrada de probabilidad): a partir de datos históricos y contexto del partido se simula el resultado, y de esa simulación surgen las probabilidades por mercado (1X2, doble oportunidad, DNB, goles, BTTS, corners). Esas probabilidades se comparan luego contra la cuota de la casa de apuestas para detectar *value bets*.

La fuente principal de datos es **Adam Choi** (como se ha usado hasta ahora), pero el modelo está abierto a incorporar más fuentes/variables si eso mejora la precisión de la simulación — es una decisión abierta a evaluar sobre la marcha, no cerrada de antemano.

El objetivo no es solo "encontrar cuotas mal calibradas" — es que la predicción en sí sea lo más precisa posible, y que el valor esperado surja de ahí. Cada predicción se puede verificar después contra el resultado real, y esa verificación retroalimenta el propio modelo (backtesting → calibración empírica → mejores predicciones).

Aunque hoy es una herramienta de análisis, la meta de fondo es que llegue a ser lo bastante confiable como para usarse con apuestas reales — no se descarta automatizar más adelante si la precisión lo justifica.

## Alcance

Lo que Beet hace:

- Calcula probabilidades crudas por mercado a partir de datos históricos y contexto del partido (forma, historial, posición en tabla).
- Calibra esas probabilidades contra resultados reales pasados (por bin de cuota, por racha, por tendencia).
- Compara probabilidad calibrada vs. cuota de mercado para detectar value bets.
- Registra cada predicción y su resultado real, para poder hacer backtesting y mejorar la calibración con el tiempo.
- Expone un dashboard para correr análisis de partidos y revisar resultados.

Lo que Beet **no** hace (fuera de alcance, al menos por ahora):

- No coloca apuestas automáticamente ni se conecta a casas de apuestas — es una herramienta de análisis, no un bot de ejecución.
- No es un tipster ni da garantías de resultado — comunica probabilidad y valor esperado, no certezas.
- No cubre todos los deportes — el foco actual es fútbol.


## Estado actual

En reconstrucción activa (arquitectura v2). Aún no hay código en el repositorio — se está definiendo el diseño antes de implementar.