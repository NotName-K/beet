# Beet

Modelo de predicción y detección de apuestas de valor.

## Visión

Beet analiza partidos de fútbol y calcula, para múltiples mercados (1X2, doble oportunidad, DNB, goles, BTTS, corners), la diferencia entre la probabilidad real estimada de un resultado y la probabilidad implícita en la cuota de la casa de apuestas. Cuando esa diferencia es favorable, la señala como *value bet*.

El objetivo no es "acertar más partidos" — es **encontrar sistemáticamente cuotas mal calibradas por la casa**, y hacerlo de forma medible: cada predicción se puede verificar después contra el resultado real, y esa verificación retroalimenta el propio modelo (backtesting → calibración empírica → mejores predicciones).

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
