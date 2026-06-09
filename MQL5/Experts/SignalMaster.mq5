//+------------------------------------------------------------------+
//| SignalMaster.mq5 — Multi-indicator, multi-timeframe signal writer |
//| Attach to ANY chart. Writes one CSV per indicator+TF+symbol.      |
//| Output: <SYMBOL>_<indicator>_<TF>.csv in Common/Files (symlinked) |
//+------------------------------------------------------------------+
#property copyright "MT5-Docker"
#property version   "2.00"
#property strict

#define MAX_INST    50
#define LOOKBACK    500

//=== Input Parameters ================================================
//  Format: "TF_minutes:param1:param2, ..." — leave empty to disable
input string INP_UTBot       = "1:10:2.0, 2:10:2.0, 3:10:2.0, 5:10:2.0, 10:10:2.0, 15:10:2.0, 30:10:2.0, 45:10:2.0, 60:10:2.0, 240:10:2.0"; // UT Bot → TF:ATR_Period:ATR_Mult
input string INP_DC          = "1:20:0, 2:20:0, 3:20:0, 5:20:0, 10:20:0, 15:20:0, 30:20:0, 45:20:0, 60:20:0, 240:20:0";             // DC Chan → TF:Length:Offset
input string INP_LiqGrab     = "3:50:5:2.0:5:100, 5:50:5:2.0:5:100, 15:50:5:2.0:5:100, 60:50:5:2.0:5:200, 240:50:5:2.0:5:200"; // LiqGrab → TF:LookbackRange:BarsN:WickBodyRatio:CandlesBeforeBreakout:MAPeriod
input string INP_EMA         = "1:9, 1:21, 1:50, 1:200, 2:9, 2:21, 2:50, 2:200, 3:9, 3:21, 3:50, 3:200, 5:9, 5:21, 5:50, 5:200, 10:9, 10:21, 10:50, 10:200, 15:9, 15:21, 15:50, 15:200, 30:9, 30:21, 30:50, 30:200, 60:9, 60:21, 60:50, 60:200, 240:9, 240:21, 240:50, 240:200"; // EMA → TF:Period
input string INP_RSI         = "1:14, 1:2, 2:14, 2:2, 3:14, 3:2, 5:14, 5:2, 10:14, 10:2, 15:14, 15:2, 30:14, 30:2, 60:14, 60:2, 240:14, 240:2";  // RSI → TF:Period
input string INP_BB          = "1:20:2.0, 2:20:2.0, 3:20:2.0, 5:20:2.0, 10:20:2.0, 15:20:2.0, 30:20:2.0, 60:20:2.0, 240:20:2.0"; // Bollinger → TF:Period:Deviation
input string INP_ADX         = "1:14, 2:14, 3:14, 5:14, 10:14, 15:14, 30:14, 60:14, 240:14";  // ADX → TF:Period
input string INP_MACD        = "1:12:26:9, 2:12:26:9, 3:12:26:9, 5:12:26:9, 10:12:26:9, 15:12:26:9, 30:12:26:9, 60:12:26:9, 240:12:26:9"; // MACD → TF:Fast:Slow:Signal
input string INP_STOCH       = "1:5:3:3, 2:5:3:3, 3:5:3:3, 5:5:3:3, 10:5:3:3, 15:5:3:3, 30:5:3:3, 60:5:3:3, 240:5:3:3"; // Stochastic → TF:K:D:Slowing
input string INP_ATR         = "1:14, 2:14, 3:14, 5:14, 10:14, 15:14, 30:14, 60:14, 240:14";  // ATR → TF:Period
input string INP_VWAP        = "1, 2, 3, 5, 10, 15, 30, 60, 240";  // VWAP → TF
input string INP_Candle      = "1, 2, 3, 5, 10, 15, 30, 45, 60, 240";  // Candle → TF
input int    WriteInterval   = 5;   // File write interval (seconds)

//=== UT Bot state ====================================================
int    g_utbot_count = 0;
int    g_utbot_tf[MAX_INST];
int    g_utbot_atr_period[MAX_INST];
double g_utbot_atr_mult[MAX_INST];
int    g_utbot_atr_handle[MAX_INST];

//=== DC Channel state ================================================
int    g_dc_count = 0;
int    g_dc_tf[MAX_INST];
int    g_dc_length[MAX_INST];
int    g_dc_offset[MAX_INST];

//=== Liquidity Grab state ============================================
int    g_liq_count = 0;
int    g_liq_tf[MAX_INST];
int    g_liq_lookback[MAX_INST];      // Range for finding key levels
int    g_liq_barsN[MAX_INST];         // Bars for rejection confirmation
double g_liq_wick_ratio[MAX_INST];    // Min wick:body ratio for rejection
int    g_liq_candles_bk[MAX_INST];    // Lookback for recent rejections before breakout
int    g_liq_ma_period[MAX_INST];     // MA period for trend filter
int    g_liq_ma_handle[MAX_INST];

//=== EMA state =======================================================
int    g_ema_count = 0;
int    g_ema_tf[MAX_INST];
int    g_ema_period[MAX_INST];
int    g_ema_handle[MAX_INST];

//=== RSI state =======================================================
int    g_rsi_count = 0;
int    g_rsi_tf[MAX_INST];
int    g_rsi_period[MAX_INST];
int    g_rsi_handle[MAX_INST];

//=== Bollinger Bands state ===========================================
int    g_bb_count = 0;
int    g_bb_tf[MAX_INST];
int    g_bb_period[MAX_INST];
double g_bb_deviation[MAX_INST];
int    g_bb_handle[MAX_INST];

//=== ADX state =======================================================
int    g_adx_count = 0;
int    g_adx_tf[MAX_INST];
int    g_adx_period[MAX_INST];
int    g_adx_handle[MAX_INST];

//=== MACD state ======================================================
int    g_macd_count = 0;
int    g_macd_tf[MAX_INST];
int    g_macd_fast[MAX_INST];
int    g_macd_slow[MAX_INST];
int    g_macd_signal[MAX_INST];
int    g_macd_handle[MAX_INST];

//=== Stochastic state ================================================
int    g_stoch_count = 0;
int    g_stoch_tf[MAX_INST];
int    g_stoch_k[MAX_INST];
int    g_stoch_d[MAX_INST];
int    g_stoch_slowing[MAX_INST];
int    g_stoch_handle[MAX_INST];

//=== ATR state (standalone) ==========================================
int    g_atr_count = 0;
int    g_atr_tf[MAX_INST];
int    g_atr_period[MAX_INST];
int    g_atr_handle[MAX_INST];

//=== VWAP state ======================================================
int    g_vwap_count = 0;
int    g_vwap_tf[MAX_INST];

//=== Candle state ====================================================
int    g_candle_count = 0;
int    g_candle_tf[MAX_INST];

//+------------------------------------------------------------------+
//| Initialization                                                     |
//+------------------------------------------------------------------+
int OnInit()
{
   ParseUTBotConfig(INP_UTBot);
   ParseDCConfig(INP_DC);
   ParseLiqGrabConfig(INP_LiqGrab);
   ParseEMAConfig(INP_EMA);
   ParseRSIConfig(INP_RSI);
   ParseBBConfig(INP_BB);
   ParseADXConfig(INP_ADX);
   ParseMACDConfig(INP_MACD);
   ParseStochConfig(INP_STOCH);
   ParseATRConfig(INP_ATR);
   ParseVWAPConfig(INP_VWAP);
   ParseCandleConfig(INP_Candle);

   for(int i = 0; i < g_utbot_count; i++)
   {
      if(IsNativeTF(g_utbot_tf[i]))
         g_utbot_atr_handle[i] = iATR(_Symbol, MinToTF(g_utbot_tf[i]), g_utbot_atr_period[i]);
      else
         g_utbot_atr_handle[i] = INVALID_HANDLE;
   }

   for(int i = 0; i < g_liq_count; i++)
   {
      if(IsNativeTF(g_liq_tf[i]))
         g_liq_ma_handle[i] = iMA(_Symbol, MinToTF(g_liq_tf[i]), g_liq_ma_period[i], 0, MODE_SMA, PRICE_CLOSE);
      else
         g_liq_ma_handle[i] = INVALID_HANDLE;
   }

   for(int i = 0; i < g_ema_count; i++)
      g_ema_handle[i] = iMA(_Symbol, MinToTF(g_ema_tf[i]), g_ema_period[i], 0, MODE_EMA, PRICE_CLOSE);

   for(int i = 0; i < g_rsi_count; i++)
      g_rsi_handle[i] = iRSI(_Symbol, MinToTF(g_rsi_tf[i]), g_rsi_period[i], PRICE_CLOSE);

   for(int i = 0; i < g_bb_count; i++)
      g_bb_handle[i] = iBands(_Symbol, MinToTF(g_bb_tf[i]), g_bb_period[i], 0, g_bb_deviation[i], PRICE_CLOSE);

   for(int i = 0; i < g_adx_count; i++)
      g_adx_handle[i] = iADX(_Symbol, MinToTF(g_adx_tf[i]), g_adx_period[i]);

   for(int i = 0; i < g_macd_count; i++)
      g_macd_handle[i] = iMACD(_Symbol, MinToTF(g_macd_tf[i]), g_macd_fast[i], g_macd_slow[i], g_macd_signal[i], PRICE_CLOSE);

   for(int i = 0; i < g_stoch_count; i++)
      g_stoch_handle[i] = iStochastic(_Symbol, MinToTF(g_stoch_tf[i]), g_stoch_k[i], g_stoch_d[i], g_stoch_slowing[i], MODE_SMA, STO_LOWHIGH);

   for(int i = 0; i < g_atr_count; i++)
      g_atr_handle[i] = iATR(_Symbol, MinToTF(g_atr_tf[i]), g_atr_period[i]);

   EventSetTimer(WriteInterval);
   Print("SignalMaster started: ", _Symbol,
         " | UTBot[", g_utbot_count, "] DC[", g_dc_count, "] LiqGrab[", g_liq_count,
         "] EMA[", g_ema_count, "] RSI[", g_rsi_count, "] BB[", g_bb_count,
         "] ADX[", g_adx_count, "] MACD[", g_macd_count, "] Stoch[", g_stoch_count,
         "] ATR[", g_atr_count, "] VWAP[", g_vwap_count,
         "] Candle[", g_candle_count, "]");

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   for(int i = 0; i < g_utbot_count; i++)
      if(g_utbot_atr_handle[i] != INVALID_HANDLE)
         IndicatorRelease(g_utbot_atr_handle[i]);
   for(int i = 0; i < g_liq_count; i++)
      if(g_liq_ma_handle[i] != INVALID_HANDLE)
         IndicatorRelease(g_liq_ma_handle[i]);
   for(int i = 0; i < g_ema_count; i++)
      IndicatorRelease(g_ema_handle[i]);
   for(int i = 0; i < g_rsi_count; i++)
      IndicatorRelease(g_rsi_handle[i]);
   for(int i = 0; i < g_bb_count; i++)
      IndicatorRelease(g_bb_handle[i]);
   for(int i = 0; i < g_adx_count; i++)
      IndicatorRelease(g_adx_handle[i]);
   for(int i = 0; i < g_macd_count; i++)
      IndicatorRelease(g_macd_handle[i]);
   for(int i = 0; i < g_stoch_count; i++)
      IndicatorRelease(g_stoch_handle[i]);
   for(int i = 0; i < g_atr_count; i++)
      IndicatorRelease(g_atr_handle[i]);
}

void OnTick()  { /* computed on timer only */ }
void OnTimer() { WriteAllSignals(); }

//+------------------------------------------------------------------+
//| Write all indicator signals                                        |
//+------------------------------------------------------------------+
void WriteAllSignals()
{
   for(int i = 0; i < g_utbot_count; i++)
      WriteUTBotSignal(i);
   for(int i = 0; i < g_dc_count; i++)
      WriteDCSignal(i);
   for(int i = 0; i < g_liq_count; i++)
      WriteLiqGrabSignal(i);
   for(int i = 0; i < g_ema_count; i++)
      WriteEMASignal(i);
   for(int i = 0; i < g_rsi_count; i++)
      WriteRSISignal(i);
   for(int i = 0; i < g_bb_count; i++)
      WriteBBSignal(i);
   for(int i = 0; i < g_adx_count; i++)
      WriteADXSignal(i);
   for(int i = 0; i < g_macd_count; i++)
      WriteMACDSignal(i);
   for(int i = 0; i < g_stoch_count; i++)
      WriteStochSignal(i);
   for(int i = 0; i < g_atr_count; i++)
      WriteATRSignal(i);
   for(int i = 0; i < g_vwap_count; i++)
      WriteVWAPSignal(i);
   for(int i = 0; i < g_candle_count; i++)
      WriteCandleSignal(i);
}

//=====================================================================
//  CONFIG PARSING
//=====================================================================
void ParseUTBotConfig(string config)
{
   if(StringLen(config) == 0) return;
   string items[];
   int count = StringSplit(config, ',', items);
   g_utbot_count = MathMin(count, MAX_INST);

   for(int i = 0; i < g_utbot_count; i++)
   {
      StringTrimLeft(items[i]);
      StringTrimRight(items[i]);
      string parts[];
      StringSplit(items[i], ':', parts);
      g_utbot_tf[i]         = (int)StringToInteger(parts[0]);
      g_utbot_atr_period[i] = (ArraySize(parts) > 1) ? (int)StringToInteger(parts[1]) : 10;
      g_utbot_atr_mult[i]   = (ArraySize(parts) > 2) ? StringToDouble(parts[2]) : 2.0;
   }
}

void ParseDCConfig(string config)
{
   if(StringLen(config) == 0) return;
   string items[];
   int count = StringSplit(config, ',', items);
   g_dc_count = MathMin(count, MAX_INST);

   for(int i = 0; i < g_dc_count; i++)
   {
      StringTrimLeft(items[i]);
      StringTrimRight(items[i]);
      string parts[];
      StringSplit(items[i], ':', parts);
      g_dc_tf[i]     = (int)StringToInteger(parts[0]);
      g_dc_length[i] = (ArraySize(parts) > 1) ? (int)StringToInteger(parts[1]) : 20;
      g_dc_offset[i] = (ArraySize(parts) > 2) ? (int)StringToInteger(parts[2]) : 0;
   }
}

void ParseLiqGrabConfig(string config)
{
   if(StringLen(config) == 0) return;
   string items[];
   int count = StringSplit(config, ',', items);
   g_liq_count = MathMin(count, MAX_INST);

   for(int i = 0; i < g_liq_count; i++)
   {
      StringTrimLeft(items[i]);
      StringTrimRight(items[i]);
      string parts[];
      StringSplit(items[i], ':', parts);
      g_liq_tf[i]          = (int)StringToInteger(parts[0]);
      g_liq_lookback[i]    = (ArraySize(parts) > 1) ? (int)StringToInteger(parts[1]) : 50;
      g_liq_barsN[i]       = (ArraySize(parts) > 2) ? (int)StringToInteger(parts[2]) : 5;
      g_liq_wick_ratio[i]  = (ArraySize(parts) > 3) ? StringToDouble(parts[3]) : 2.0;
      g_liq_candles_bk[i]  = (ArraySize(parts) > 4) ? (int)StringToInteger(parts[4]) : 5;
      g_liq_ma_period[i]   = (ArraySize(parts) > 5) ? (int)StringToInteger(parts[5]) : 100;
   }
}

void ParseEMAConfig(string config)
{
   if(StringLen(config) == 0) return;
   string items[];
   int count = StringSplit(config, ',', items);
   g_ema_count = MathMin(count, MAX_INST);
   for(int i = 0; i < g_ema_count; i++)
   {
      StringTrimLeft(items[i]); StringTrimRight(items[i]);
      string parts[];
      StringSplit(items[i], ':', parts);
      g_ema_tf[i]     = (int)StringToInteger(parts[0]);
      g_ema_period[i] = (ArraySize(parts) > 1) ? (int)StringToInteger(parts[1]) : 20;
   }
}

void ParseRSIConfig(string config)
{
   if(StringLen(config) == 0) return;
   string items[];
   int count = StringSplit(config, ',', items);
   g_rsi_count = MathMin(count, MAX_INST);
   for(int i = 0; i < g_rsi_count; i++)
   {
      StringTrimLeft(items[i]); StringTrimRight(items[i]);
      string parts[];
      StringSplit(items[i], ':', parts);
      g_rsi_tf[i]     = (int)StringToInteger(parts[0]);
      g_rsi_period[i] = (ArraySize(parts) > 1) ? (int)StringToInteger(parts[1]) : 14;
   }
}

void ParseBBConfig(string config)
{
   if(StringLen(config) == 0) return;
   string items[];
   int count = StringSplit(config, ',', items);
   g_bb_count = MathMin(count, MAX_INST);
   for(int i = 0; i < g_bb_count; i++)
   {
      StringTrimLeft(items[i]); StringTrimRight(items[i]);
      string parts[];
      StringSplit(items[i], ':', parts);
      g_bb_tf[i]        = (int)StringToInteger(parts[0]);
      g_bb_period[i]    = (ArraySize(parts) > 1) ? (int)StringToInteger(parts[1]) : 20;
      g_bb_deviation[i] = (ArraySize(parts) > 2) ? StringToDouble(parts[2]) : 2.0;
   }
}

void ParseADXConfig(string config)
{
   if(StringLen(config) == 0) return;
   string items[];
   int count = StringSplit(config, ',', items);
   g_adx_count = MathMin(count, MAX_INST);
   for(int i = 0; i < g_adx_count; i++)
   {
      StringTrimLeft(items[i]); StringTrimRight(items[i]);
      string parts[];
      StringSplit(items[i], ':', parts);
      g_adx_tf[i]     = (int)StringToInteger(parts[0]);
      g_adx_period[i] = (ArraySize(parts) > 1) ? (int)StringToInteger(parts[1]) : 14;
   }
}

void ParseMACDConfig(string config)
{
   if(StringLen(config) == 0) return;
   string items[];
   int count = StringSplit(config, ',', items);
   g_macd_count = MathMin(count, MAX_INST);
   for(int i = 0; i < g_macd_count; i++)
   {
      StringTrimLeft(items[i]); StringTrimRight(items[i]);
      string parts[];
      StringSplit(items[i], ':', parts);
      g_macd_tf[i]     = (int)StringToInteger(parts[0]);
      g_macd_fast[i]   = (ArraySize(parts) > 1) ? (int)StringToInteger(parts[1]) : 12;
      g_macd_slow[i]   = (ArraySize(parts) > 2) ? (int)StringToInteger(parts[2]) : 26;
      g_macd_signal[i] = (ArraySize(parts) > 3) ? (int)StringToInteger(parts[3]) : 9;
   }
}

void ParseStochConfig(string config)
{
   if(StringLen(config) == 0) return;
   string items[];
   int count = StringSplit(config, ',', items);
   g_stoch_count = MathMin(count, MAX_INST);
   for(int i = 0; i < g_stoch_count; i++)
   {
      StringTrimLeft(items[i]); StringTrimRight(items[i]);
      string parts[];
      StringSplit(items[i], ':', parts);
      g_stoch_tf[i]      = (int)StringToInteger(parts[0]);
      g_stoch_k[i]       = (ArraySize(parts) > 1) ? (int)StringToInteger(parts[1]) : 5;
      g_stoch_d[i]       = (ArraySize(parts) > 2) ? (int)StringToInteger(parts[2]) : 3;
      g_stoch_slowing[i] = (ArraySize(parts) > 3) ? (int)StringToInteger(parts[3]) : 3;
   }
}

void ParseATRConfig(string config)
{
   if(StringLen(config) == 0) return;
   string items[];
   int count = StringSplit(config, ',', items);
   g_atr_count = MathMin(count, MAX_INST);
   for(int i = 0; i < g_atr_count; i++)
   {
      StringTrimLeft(items[i]); StringTrimRight(items[i]);
      string parts[];
      StringSplit(items[i], ':', parts);
      g_atr_tf[i]     = (int)StringToInteger(parts[0]);
      g_atr_period[i] = (ArraySize(parts) > 1) ? (int)StringToInteger(parts[1]) : 14;
   }
}

void ParseVWAPConfig(string config)
{
   if(StringLen(config) == 0) return;
   string items[];
   int count = StringSplit(config, ',', items);
   g_vwap_count = MathMin(count, MAX_INST);
   for(int i = 0; i < g_vwap_count; i++)
   {
      StringTrimLeft(items[i]); StringTrimRight(items[i]);
      g_vwap_tf[i] = (int)StringToInteger(items[i]);
   }
}

void ParseCandleConfig(string config)
{
   if(StringLen(config) == 0) return;
   string items[];
   int count = StringSplit(config, ',', items);
   g_candle_count = MathMin(count, MAX_INST);
   for(int i = 0; i < g_candle_count; i++)
   {
      StringTrimLeft(items[i]); StringTrimRight(items[i]);
      g_candle_tf[i] = (int)StringToInteger(items[i]);
   }
}

//=====================================================================
//  TIMEFRAME UTILITIES
//=====================================================================
bool IsNativeTF(int minutes)
{
   int native[] = {1,2,3,4,5,6,10,12,15,20,30,60,120,180,240,360,480,720,1440};
   for(int i = 0; i < ArraySize(native); i++)
      if(native[i] == minutes) return true;
   return false;
}

ENUM_TIMEFRAMES MinToTF(int m)
{
   switch(m)
   {
      case 1:    return PERIOD_M1;   case 2:    return PERIOD_M2;
      case 3:    return PERIOD_M3;   case 4:    return PERIOD_M4;
      case 5:    return PERIOD_M5;   case 6:    return PERIOD_M6;
      case 10:   return PERIOD_M10;  case 12:   return PERIOD_M12;
      case 15:   return PERIOD_M15;  case 20:   return PERIOD_M20;
      case 30:   return PERIOD_M30;  case 60:   return PERIOD_H1;
      case 120:  return PERIOD_H2;   case 180:  return PERIOD_H3;
      case 240:  return PERIOD_H4;   case 360:  return PERIOD_H6;
      case 480:  return PERIOD_H8;   case 720:  return PERIOD_H12;
      case 1440: return PERIOD_D1;
      default:   return PERIOD_M1;
   }
}

string TFToString(int minutes)
{
   if(minutes < 60) return "M" + IntegerToString(minutes);
   if(minutes < 1440) return "H" + IntegerToString(minutes / 60);
   return "D1";
}

//=====================================================================
//  SYNTHETIC BAR BUILDER  (for non-native TFs like 45m)
//=====================================================================
int BuildSyntheticBars(int tf_minutes, int bars_needed,
                       double &opens[], double &highs[],
                       double &lows[],  double &closes[],
                       long &volumes[], datetime &times[])
{
   int m1_needed = bars_needed * tf_minutes + tf_minutes;
   MqlRates m1_rates[];
   ArraySetAsSeries(m1_rates, false);
   int copied = CopyRates(_Symbol, PERIOD_M1, 0, m1_needed, m1_rates);
   if(copied < tf_minutes * 3) return 0;

   int bar_count = copied / tf_minutes;
   ArrayResize(opens, bar_count);
   ArrayResize(highs, bar_count);
   ArrayResize(lows, bar_count);
   ArrayResize(closes, bar_count);
   ArrayResize(volumes, bar_count);
   ArrayResize(times, bar_count);

   for(int b = 0; b < bar_count; b++)
   {
      int start = b * tf_minutes;
      int end   = MathMin(start + tf_minutes, copied);

      opens[b]   = m1_rates[start].open;
      highs[b]   = m1_rates[start].high;
      lows[b]    = m1_rates[start].low;
      closes[b]  = m1_rates[end - 1].close;
      volumes[b] = 0;
      times[b]   = m1_rates[start].time;

      for(int j = start; j < end; j++)
      {
         if(m1_rates[j].high > highs[b]) highs[b] = m1_rates[j].high;
         if(m1_rates[j].low  < lows[b])  lows[b]  = m1_rates[j].low;
         volumes[b] += m1_rates[j].tick_volume;
      }
   }
   return bar_count;
}

//=====================================================================
//  MANUAL ATR  (Wilder smoothing, for synthetic TFs)
//=====================================================================
void ComputeATR(const double &highs[], const double &lows[],
                const double &closes[], int period, double &atr[], int total)
{
   ArrayResize(atr, total);
   ArrayInitialize(atr, 0);
   if(total < period + 1) return;

   // First TR values + initial ATR as simple average
   double sum = 0;
   for(int i = 1; i <= period; i++)
   {
      double tr = MathMax(highs[i] - lows[i],
                  MathMax(MathAbs(highs[i] - closes[i - 1]),
                          MathAbs(lows[i]  - closes[i - 1])));
      atr[i] = tr;
      sum += tr;
   }
   atr[period] = sum / period;

   // Wilder smoothing
   for(int i = period + 1; i < total; i++)
   {
      double tr = MathMax(highs[i] - lows[i],
                  MathMax(MathAbs(highs[i] - closes[i - 1]),
                          MathAbs(lows[i]  - closes[i - 1])));
      atr[i] = (atr[i - 1] * (period - 1) + tr) / period;
   }
}

//=====================================================================
//  STANDARD CSV HEADER  (written to every file)
//=====================================================================
void WriteStdHeader(int handle, string indicator, int tf_minutes)
{
   MqlTick tick;
   SymbolInfoTick(_Symbol, tick);

   FileWrite(handle, "key", "value");
   FileWrite(handle, "symbol",             _Symbol);
   FileWrite(handle, "indicator",          indicator);
   FileWrite(handle, "timeframe",          TFToString(tf_minutes));
   FileWrite(handle, "timeframe_minutes",  IntegerToString(tf_minutes));
   FileWrite(handle, "server_time",        TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS));
   FileWrite(handle, "bid",                DoubleToString(tick.bid, _Digits));
   FileWrite(handle, "ask",                DoubleToString(tick.ask, _Digits));
   FileWrite(handle, "spread",             DoubleToString(tick.ask - tick.bid, _Digits));
}

void WriteBarFields(int handle, string prefix,
                    double open, double high, double low, double close,
                    datetime time, long volume)
{
   FileWrite(handle, prefix + "_bar_time",   TimeToString(time, TIME_DATE | TIME_SECONDS));
   FileWrite(handle, prefix + "_open",       DoubleToString(open, _Digits));
   FileWrite(handle, prefix + "_high",       DoubleToString(high, _Digits));
   FileWrite(handle, prefix + "_low",        DoubleToString(low, _Digits));
   FileWrite(handle, prefix + "_close",      DoubleToString(close, _Digits));
   FileWrite(handle, prefix + "_volume",     IntegerToString(volume));
}

//=====================================================================
//  UT BOT — compute + write
//=====================================================================
void WriteUTBotSignal(int idx)
{
   int    tf_min  = g_utbot_tf[idx];
   int    atr_per = g_utbot_atr_period[idx];
   double atr_mul = g_utbot_atr_mult[idx];

   double close_arr[], atr_arr[];
   double open_arr[], high_arr[], low_arr[];
   datetime time_arr[];
   long vol_arr[];
   int total = 0;

   //--- Get bar data + ATR
   if(IsNativeTF(tf_min))
   {
      ENUM_TIMEFRAMES tf = MinToTF(tf_min);
      total = MathMin(Bars(_Symbol, tf), LOOKBACK);
      if(total < atr_per + 3) return;

      ArraySetAsSeries(open_arr, false);
      ArraySetAsSeries(high_arr, false);
      ArraySetAsSeries(low_arr, false);
      ArraySetAsSeries(close_arr, false);
      ArraySetAsSeries(atr_arr, false);
      ArraySetAsSeries(time_arr, false);

      MqlRates rates[];
      ArraySetAsSeries(rates, false);
      if(CopyRates(_Symbol, tf, 0, total, rates) < total) return;
      if(CopyBuffer(g_utbot_atr_handle[idx], 0, 0, total, atr_arr) < total) return;

      ArrayResize(open_arr, total);
      ArrayResize(high_arr, total);
      ArrayResize(low_arr, total);
      ArrayResize(close_arr, total);
      ArrayResize(time_arr, total);
      ArrayResize(vol_arr, total);

      for(int i = 0; i < total; i++)
      {
         open_arr[i]  = rates[i].open;
         high_arr[i]  = rates[i].high;
         low_arr[i]   = rates[i].low;
         close_arr[i] = rates[i].close;
         time_arr[i]  = rates[i].time;
         vol_arr[i]   = rates[i].tick_volume;
      }
   }
   else
   {
      total = BuildSyntheticBars(tf_min, LOOKBACK, open_arr, high_arr, low_arr, close_arr, vol_arr, time_arr);
      if(total < atr_per + 3) return;
      ComputeATR(high_arr, low_arr, close_arr, atr_per, atr_arr, total);
   }

   //--- Compute trail stop + direction
   double trail_stop[], direction[];
   ArrayResize(trail_stop, total);
   ArrayResize(direction, total);

   for(int i = 0; i < atr_per && i < total; i++)
   {
      trail_stop[i] = close_arr[i];
      direction[i]  = 1;
   }

   for(int i = atr_per; i < total; i++)
   {
      double nLoss     = atr_mul * atr_arr[i];
      double prev_stop = trail_stop[i - 1];
      double prev_dir  = direction[i - 1];

      if(close_arr[i] > prev_stop)
      {
         trail_stop[i] = close_arr[i] - nLoss;
         if(prev_dir > 0) trail_stop[i] = MathMax(trail_stop[i], prev_stop);
         direction[i] = 1;
      }
      else
      {
         trail_stop[i] = close_arr[i] + nLoss;
         if(prev_dir < 0) trail_stop[i] = MathMin(trail_stop[i], prev_stop);
         direction[i] = -1;
      }
   }

   //--- Extract running / closed / prev indices
   int run  = total - 1;   // current forming bar
   int cls  = total - 2;   // last completed bar
   int prev = total - 3;   // bar before closed

   string running_bias   = (direction[run] > 0) ? "BULLISH" : "BEARISH";
   string running_signal = "NONE";
   if(direction[run] > 0 && direction[cls] < 0) running_signal = "BUY";
   if(direction[run] < 0 && direction[cls] > 0) running_signal = "SELL";

   string closed_bias   = (direction[cls] > 0) ? "BULLISH" : "BEARISH";
   string closed_signal = "NONE";
   if(prev >= 0)
   {
      if(direction[cls] > 0 && direction[prev] < 0) closed_signal = "BUY";
      if(direction[cls] < 0 && direction[prev] > 0) closed_signal = "SELL";
   }

   //--- Consecutive bar counts
   int consec_bull = 0, consec_bear = 0;
   for(int i = run; i >= 0; i--)
   {
      if(direction[i] > 0) { if(consec_bear > 0) break; consec_bull++; }
      else                 { if(consec_bull > 0) break; consec_bear++; }
   }

   //--- Write CSV
   string filename = _Symbol + "_utbot_" + TFToString(tf_min) + ".csv";
   int handle = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_COMMON, ',');
   if(handle == INVALID_HANDLE) return;

   WriteStdHeader(handle, "utbot", tf_min);

   // Running bar OHLCV
   WriteBarFields(handle, "running", open_arr[run], high_arr[run], low_arr[run],
                  close_arr[run], time_arr[run], vol_arr[run]);
   // Closed bar OHLCV
   WriteBarFields(handle, "closed", open_arr[cls], high_arr[cls], low_arr[cls],
                  close_arr[cls], time_arr[cls], vol_arr[cls]);

   // UT Bot indicator values — running
   FileWrite(handle, "running_atr",           DoubleToString(atr_arr[run], _Digits));
   FileWrite(handle, "running_nloss",         DoubleToString(atr_mul * atr_arr[run], _Digits));
   FileWrite(handle, "running_trail_stop",    DoubleToString(trail_stop[run], _Digits));
   FileWrite(handle, "running_bias",          running_bias);
   FileWrite(handle, "running_signal",        running_signal);

   // UT Bot indicator values — closed
   FileWrite(handle, "closed_atr",            DoubleToString(atr_arr[cls], _Digits));
   FileWrite(handle, "closed_nloss",          DoubleToString(atr_mul * atr_arr[cls], _Digits));
   FileWrite(handle, "closed_trail_stop",     DoubleToString(trail_stop[cls], _Digits));
   FileWrite(handle, "closed_bias",           closed_bias);
   FileWrite(handle, "closed_signal",         closed_signal);

   // Streak info
   FileWrite(handle, "consecutive_bull_bars", IntegerToString(consec_bull));
   FileWrite(handle, "consecutive_bear_bars", IntegerToString(consec_bear));

   // Config echo (so reader knows what params produced this)
   FileWrite(handle, "cfg_atr_period",        IntegerToString(atr_per));
   FileWrite(handle, "cfg_atr_mult",          DoubleToString(atr_mul, 1));

   FileClose(handle);
}

//=====================================================================
//  DONCHIAN CHANNEL — compute + write
//=====================================================================
void WriteDCSignal(int idx)
{
   int tf_min = g_dc_tf[idx];
   int length = g_dc_length[idx];
   int offset = g_dc_offset[idx];

   double upper = 0, lower = 0, mid = 0;
   double dc_width_sma20 = 0;
   double run_open = 0, run_high = 0, run_low = 0, run_close = 0;
   double cls_open = 0, cls_high = 0, cls_low = 0, cls_close = 0;
   datetime run_time = 0, cls_time = 0;
   long run_vol = 0, cls_vol = 0;

   if(IsNativeTF(tf_min))
   {
      ENUM_TIMEFRAMES tf = MinToTF(tf_min);
      int bars_needed = length + offset + 22;  // +22 for width SMA computation

      double highs[], lows[];
      ArraySetAsSeries(highs, true);
      ArraySetAsSeries(lows, true);

      if(CopyHigh(_Symbol, tf, 0, bars_needed, highs) < bars_needed) return;
      if(CopyLow(_Symbol, tf, 0, bars_needed, lows) < bars_needed) return;

      // Current DC from bars [offset+1 .. offset+length] (series order, 0=newest)
      double dc_hi = -DBL_MAX, dc_lo = DBL_MAX;
      for(int i = offset + 1; i <= offset + length; i++)
      {
         if(highs[i] > dc_hi) dc_hi = highs[i];
         if(lows[i] < dc_lo)  dc_lo = lows[i];
      }
      upper = dc_hi;
      lower = dc_lo;
      mid   = (upper + lower) / 2.0;

      // Compute DC width at each of last 20 shifted bars for SMA
      // Bar k's DC window: [offset+1+k .. offset+length+k]
      double width_sum = 0;
      for(int k = 1; k <= 20; k++)
      {
         double hi_k = -DBL_MAX, lo_k = DBL_MAX;
         for(int j = offset + 1 + k; j <= offset + length + k && j < bars_needed; j++)
         {
            if(highs[j] > hi_k) hi_k = highs[j];
            if(lows[j] < lo_k)  lo_k = lows[j];
         }
         width_sum += (hi_k - lo_k);
      }
      dc_width_sma20 = width_sum / 20.0;

      // Get running + closed bars
      MqlRates rates[];
      ArraySetAsSeries(rates, true);
      if(CopyRates(_Symbol, tf, 0, 2, rates) < 2) return;
      // rates[0] = running (series mode), rates[1] = closed
      run_open = rates[0].open; run_high = rates[0].high;
      run_low  = rates[0].low;  run_close = rates[0].close;
      run_time = rates[0].time; run_vol  = rates[0].tick_volume;
      cls_open = rates[1].open; cls_high = rates[1].high;
      cls_low  = rates[1].low;  cls_close = rates[1].close;
      cls_time = rates[1].time; cls_vol  = rates[1].tick_volume;
   }
   else
   {
      double opens[], hi[], lo[], cl[];
      long vols[];
      datetime times[];
      int total = BuildSyntheticBars(tf_min, length + offset + 25,
                                     opens, hi, lo, cl, vols, times);
      if(total < length + offset + 22) return;

      // DC from closed synthetic bars (skip last = running)
      upper = -DBL_MAX;
      lower =  DBL_MAX;
      int start_idx = total - 2 - offset;  // start from last closed bar
      for(int i = start_idx; i > start_idx - length && i >= 0; i--)
      {
         if(hi[i] > upper) upper = hi[i];
         if(lo[i] < lower) lower = lo[i];
      }
      mid = (upper + lower) / 2.0;

      // Compute DC width SMA over 20 shifted bars
      double width_sum = 0;
      for(int k = 1; k <= 20; k++)
      {
         double hi_k = -DBL_MAX, lo_k = DBL_MAX;
         int si = start_idx - k;
         for(int j = si; j > si - length && j >= 0; j--)
         {
            if(hi[j] > hi_k) hi_k = hi[j];
            if(lo[j] < lo_k) lo_k = lo[j];
         }
         width_sum += (hi_k - lo_k);
      }
      dc_width_sma20 = width_sum / 20.0;

      int run_i = total - 1;
      int cls_i = total - 2;
      run_open = opens[run_i]; run_high = hi[run_i];
      run_low  = lo[run_i];    run_close = cl[run_i];
      run_time = times[run_i]; run_vol  = vols[run_i];
      cls_open = opens[cls_i]; cls_high = hi[cls_i];
      cls_low  = lo[cls_i];    cls_close = cl[cls_i];
      cls_time = times[cls_i]; cls_vol  = vols[cls_i];
   }

   //--- Price position within channel
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   double channel_width = upper - lower;
   double pct_running = (channel_width > 0)
      ? (tick.bid - lower) / channel_width * 100.0 : 50.0;
   double pct_closed = (channel_width > 0)
      ? (cls_close - lower) / channel_width * 100.0 : 50.0;

   string running_zone = PriceZone(pct_running);
   string closed_zone  = PriceZone(pct_closed);

   //--- Touch / breakout detection on running bar
   bool run_touch_upper = (run_high >= upper);
   bool run_touch_lower = (run_low  <= lower);
   bool run_break_upper = (run_close > upper);
   bool run_break_lower = (run_close < lower);

   //--- Touch / breakout detection on closed bar
   bool cls_touch_upper = (cls_high >= upper);
   bool cls_touch_lower = (cls_low  <= lower);
   bool cls_break_upper = (cls_close > upper);
   bool cls_break_lower = (cls_close < lower);

   //--- Wick rejection on closed bar
   double body_top    = MathMax(cls_open, cls_close);
   double body_bottom = MathMin(cls_open, cls_close);
   double upper_wick  = cls_high - body_top;
   double lower_wick  = body_bottom - cls_low;
   double body_size   = body_top - body_bottom;

   bool upper_wick_rej = cls_touch_upper && (upper_wick > body_size) && (cls_close < upper);
   bool lower_wick_rej = cls_touch_lower && (lower_wick > body_size) && (cls_close > lower);

   //--- Write CSV
   string filename = _Symbol + "_dc_" + TFToString(tf_min) + ".csv";
   int handle = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_COMMON, ',');
   if(handle == INVALID_HANDLE) return;

   WriteStdHeader(handle, "dc", tf_min);

   WriteBarFields(handle, "running", run_open, run_high, run_low, run_close, run_time, run_vol);
   WriteBarFields(handle, "closed",  cls_open, cls_high, cls_low, cls_close, cls_time, cls_vol);

   // Channel values
   FileWrite(handle, "upper_band",              DoubleToString(upper, _Digits));
   FileWrite(handle, "lower_band",              DoubleToString(lower, _Digits));
   FileWrite(handle, "mid_band",                DoubleToString(mid, _Digits));
   FileWrite(handle, "channel_width",           DoubleToString(channel_width, _Digits));

   // Running analysis
   FileWrite(handle, "running_price_zone",      running_zone);
   FileWrite(handle, "running_pct_in_channel",  DoubleToString(pct_running, 1));
   FileWrite(handle, "running_touched_upper",   run_touch_upper ? "TRUE" : "FALSE");
   FileWrite(handle, "running_touched_lower",   run_touch_lower ? "TRUE" : "FALSE");
   FileWrite(handle, "running_break_upper",     run_break_upper ? "TRUE" : "FALSE");
   FileWrite(handle, "running_break_lower",     run_break_lower ? "TRUE" : "FALSE");

   // Closed analysis
   FileWrite(handle, "closed_price_zone",       closed_zone);
   FileWrite(handle, "closed_pct_in_channel",   DoubleToString(pct_closed, 1));
   FileWrite(handle, "closed_touched_upper",    cls_touch_upper ? "TRUE" : "FALSE");
   FileWrite(handle, "closed_touched_lower",    cls_touch_lower ? "TRUE" : "FALSE");
   FileWrite(handle, "closed_break_upper",      cls_break_upper ? "TRUE" : "FALSE");
   FileWrite(handle, "closed_break_lower",      cls_break_lower ? "TRUE" : "FALSE");
   FileWrite(handle, "closed_upper_wick_rej",   upper_wick_rej ? "TRUE" : "FALSE");
   FileWrite(handle, "closed_lower_wick_rej",   lower_wick_rej ? "TRUE" : "FALSE");

   // Compression detection: current width vs 20-bar SMA of width
   double width_ratio = (dc_width_sma20 > 0) ? channel_width / dc_width_sma20 : 1.0;
   bool dc_compressed = (width_ratio < 0.75);
   FileWrite(handle, "channel_width_sma20",     DoubleToString(dc_width_sma20, _Digits));
   FileWrite(handle, "width_vs_sma_ratio",      DoubleToString(width_ratio, 2));
   FileWrite(handle, "dc_compressed",           dc_compressed ? "TRUE" : "FALSE");

   // Config echo
   FileWrite(handle, "cfg_length",              IntegerToString(length));
   FileWrite(handle, "cfg_offset",              IntegerToString(offset));

   FileClose(handle);
}

//+------------------------------------------------------------------+
string PriceZone(double pct)
{
   if(pct >= 90)      return "UPPER";
   if(pct >= 70)      return "UPPER_MID";
   if(pct <= 10)      return "LOWER";
   if(pct <= 30)      return "LOWER_MID";
   return "MIDDLE";
}

//=====================================================================
//  LIQUIDITY GRAB — compute + write
//=====================================================================

// Find key high: highest structural peak within range
double LiqFindKeyHigh(const double &highs[], const double &lows[],
                      const double &closes[], int total, int barsN, int range)
{
   double bestPeak = 0;
   bool   found = false;
   int limit = MathMin(range, total - barsN);
   for(int i = barsN; i < limit; i++)
   {
      double hi = highs[i];
      // Check if this bar is the highest in a window of 2*barsN+1
      bool isPeak = true;
      for(int j = i - barsN; j <= i + barsN && j < total; j++)
      {
         if(j < 0) continue;
         if(j != i && highs[j] > hi) { isPeak = false; break; }
      }
      if(isPeak && hi > bestPeak)
      {
         bestPeak = hi;
         found = true;
      }
   }
   return found ? bestPeak : 99999;
}

// Find key low: lowest structural trough within range
double LiqFindKeyLow(const double &highs[], const double &lows[],
                     const double &closes[], int total, int barsN, int range)
{
   double bestTrough = DBL_MAX;
   bool   found = false;
   int limit = MathMin(range, total - barsN);
   for(int i = barsN; i < limit; i++)
   {
      double lo = lows[i];
      bool isTrough = true;
      for(int j = i - barsN; j <= i + barsN && j < total; j++)
      {
         if(j < 0) continue;
         if(j != i && lows[j] < lo) { isTrough = false; break; }
      }
      if(isTrough && lo < bestTrough)
      {
         bestTrough = lo;
         found = true;
      }
   }
   return found ? bestTrough : -1;
}

// Check if bar at shift is a rejection UP (bullish — lower wick grabs liquidity)
bool LiqIsRejectionUp(const double &opens[], const double &highs[],
                      const double &lows[], const double &closes[],
                      int shift, double wickRatio, double keyLow)
{
   double open  = opens[shift];
   double close = closes[shift];
   double high  = highs[shift];
   double low   = lows[shift];
   double bodySize = MathAbs(close - open);
   if(bodySize < _Point) return false;
   double lowerWick = MathMin(open, close) - low;
   // Wick must be big enough AND candle must sweep below key low but close above it
   return (lowerWick >= wickRatio * bodySize && low < keyLow && high > keyLow);
}

// Check if bar at shift is a rejection DOWN (bearish — upper wick grabs liquidity)
bool LiqIsRejectionDown(const double &opens[], const double &highs[],
                        const double &lows[], const double &closes[],
                        int shift, double wickRatio, double keyHigh)
{
   double open  = opens[shift];
   double close = closes[shift];
   double high  = highs[shift];
   double low   = lows[shift];
   double bodySize = MathAbs(close - open);
   if(bodySize < _Point) return false;
   double upperWick = high - MathMax(open, close);
   return (upperWick >= wickRatio * bodySize && high > keyHigh && low < keyHigh);
}

void WriteLiqGrabSignal(int idx)
{
   int    tf_min      = g_liq_tf[idx];
   int    lookback    = g_liq_lookback[idx];
   int    barsN       = g_liq_barsN[idx];
   double wickRatio   = g_liq_wick_ratio[idx];
   int    candlesBk   = g_liq_candles_bk[idx];
   int    maPeriod    = g_liq_ma_period[idx];

   int bars_needed = MathMax(lookback, maPeriod) + barsN + 10;

   double opens[], highs[], lows[], closes[];
   datetime times[];
   long vols[];
   int total = 0;

   //--- Get bar data
   if(IsNativeTF(tf_min))
   {
      ENUM_TIMEFRAMES tf = MinToTF(tf_min);
      MqlRates rates[];
      ArraySetAsSeries(rates, true);  // [0]=most recent
      total = CopyRates(_Symbol, tf, 0, bars_needed, rates);
      if(total < bars_needed) return;

      ArrayResize(opens, total);  ArrayResize(highs, total);
      ArrayResize(lows, total);   ArrayResize(closes, total);
      ArrayResize(times, total);  ArrayResize(vols, total);

      for(int i = 0; i < total; i++)
      {
         opens[i]  = rates[i].open;   highs[i] = rates[i].high;
         lows[i]   = rates[i].low;    closes[i] = rates[i].close;
         times[i]  = rates[i].time;   vols[i]  = rates[i].tick_volume;
      }
   }
   else
   {
      // Build synthetic bars (returns non-series: [0]=oldest)
      double s_opens[], s_highs[], s_lows[], s_closes[];
      long s_vols[];
      datetime s_times[];
      int synth = BuildSyntheticBars(tf_min, bars_needed, s_opens, s_highs, s_lows, s_closes, s_vols, s_times);
      if(synth < bars_needed) return;

      // Reverse to series order [0]=most recent
      total = synth;
      ArrayResize(opens, total);  ArrayResize(highs, total);
      ArrayResize(lows, total);   ArrayResize(closes, total);
      ArrayResize(times, total);  ArrayResize(vols, total);

      for(int i = 0; i < total; i++)
      {
         int ri = total - 1 - i;
         opens[i] = s_opens[ri];  highs[i] = s_highs[ri];
         lows[i]  = s_lows[ri];   closes[i] = s_closes[ri];
         times[i] = s_times[ri];  vols[i]  = s_vols[ri];
      }
   }

   //--- Index 0 = running bar, 1 = last closed bar (series order)
   //--- Key levels (search from bar 1 onwards — closed bars only)
   double keyHigh = LiqFindKeyHigh(highs, lows, closes, total, barsN, lookback);
   double keyLow  = LiqFindKeyLow(highs, lows, closes, total, barsN, lookback);

   //--- Check for recent rejection (liquidity grab) in last N closed candles
   bool wasRejUp   = false;
   bool wasRejDown = false;
   int  rejUpBar   = -1;
   int  rejDownBar = -1;

   for(int i = 1; i <= candlesBk && i < total; i++)
   {
      if(!wasRejUp && LiqIsRejectionUp(opens, highs, lows, closes, i, wickRatio, keyLow))
      {
         wasRejUp = true;
         rejUpBar = i;
      }
      if(!wasRejDown && LiqIsRejectionDown(opens, highs, lows, closes, i, wickRatio, keyHigh))
      {
         wasRejDown = true;
         rejDownBar = i;
      }
   }

   //--- Breakout detection: price broke past key level on opposite side (short lookback)
   bool breakoutUp   = false;
   bool breakoutDown = false;
   double bkKeyHigh = LiqFindKeyHigh(highs, lows, closes, total, barsN, candlesBk + barsN);
   double bkKeyLow  = LiqFindKeyLow(highs, lows, closes, total, barsN, candlesBk + barsN);
   for(int i = 1; i <= candlesBk && i < total; i++)
   {
      if(closes[i] > bkKeyHigh)
         breakoutUp = true;
      if(closes[i] < bkKeyLow)
         breakoutDown = true;
   }

   //--- MA trend filter
   double maValue = 0;
   if(IsNativeTF(tf_min) && g_liq_ma_handle[idx] != INVALID_HANDLE)
   {
      double maBuf[];
      if(CopyBuffer(g_liq_ma_handle[idx], 0, 1, 1, maBuf) > 0)
         maValue = maBuf[0];
   }
   else
   {
      // Manual SMA for synthetic TFs
      double sum = 0;
      int count = MathMin(maPeriod, total - 1);
      for(int i = 1; i <= count; i++) sum += closes[i];
      if(count > 0) maValue = sum / count;
   }

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   string maTrend = (tick.bid > maValue) ? "ABOVE" : "BELOW";

   //--- Composite signal: rejection + breakout + trend alignment
   string liqSignal = "NONE";
   if(wasRejUp && breakoutUp && tick.ask > maValue)
      liqSignal = "BUY";
   else if(wasRejDown && breakoutDown && tick.bid < maValue)
      liqSignal = "SELL";

   //--- Running bar proximity to key levels
   double distToKeyHigh = (keyHigh < 99999) ? highs[0] - keyHigh : 0;
   double distToKeyLow  = (keyLow > -1) ? lows[0] - keyLow : 0;

   //--- Write CSV
   string filename = _Symbol + "_liqgrab_" + TFToString(tf_min) + ".csv";
   int handle = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_COMMON, ',');
   if(handle == INVALID_HANDLE) return;

   WriteStdHeader(handle, "liqgrab", tf_min);

   // Running + closed bar
   WriteBarFields(handle, "running", opens[0], highs[0], lows[0], closes[0], times[0], vols[0]);
   WriteBarFields(handle, "closed",  opens[1], highs[1], lows[1], closes[1], times[1], vols[1]);

   // Key levels
   FileWrite(handle, "key_high",                (keyHigh < 99999) ? DoubleToString(keyHigh, _Digits) : "NONE");
   FileWrite(handle, "key_low",                 (keyLow > -1) ? DoubleToString(keyLow, _Digits) : "NONE");
   FileWrite(handle, "dist_to_key_high",        DoubleToString(distToKeyHigh, _Digits));
   FileWrite(handle, "dist_to_key_low",         DoubleToString(distToKeyLow, _Digits));

   // Liquidity grab detection
   FileWrite(handle, "rejection_up",            wasRejUp ? "TRUE" : "FALSE");
   FileWrite(handle, "rejection_up_bar",        IntegerToString(rejUpBar));
   FileWrite(handle, "rejection_down",          wasRejDown ? "TRUE" : "FALSE");
   FileWrite(handle, "rejection_down_bar",      IntegerToString(rejDownBar));

   // Breakout
   FileWrite(handle, "breakout_up",             breakoutUp ? "TRUE" : "FALSE");
   FileWrite(handle, "breakout_down",           breakoutDown ? "TRUE" : "FALSE");

   // Trend filter
   FileWrite(handle, "ma_value",                DoubleToString(maValue, _Digits));
   FileWrite(handle, "ma_trend",                maTrend);

   // Composite signal
   FileWrite(handle, "liq_signal",              liqSignal);

   // Config echo
   FileWrite(handle, "cfg_lookback",            IntegerToString(lookback));
   FileWrite(handle, "cfg_barsN",               IntegerToString(barsN));
   FileWrite(handle, "cfg_wick_ratio",          DoubleToString(wickRatio, 1));
   FileWrite(handle, "cfg_candles_bk",          IntegerToString(candlesBk));
   FileWrite(handle, "cfg_ma_period",           IntegerToString(maPeriod));

   FileClose(handle);
}

//=====================================================================
//  EMA — compute + write
//=====================================================================
void WriteEMASignal(int idx)
{
   int tf_min = g_ema_tf[idx];
   int period = g_ema_period[idx];
   ENUM_TIMEFRAMES tf = MinToTF(tf_min);

   double ema_buf[];
   ArraySetAsSeries(ema_buf, true);
   if(CopyBuffer(g_ema_handle[idx], 0, 0, 6, ema_buf) < 6) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 0, 2, rates) < 2) return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   string price_vs_ema = (tick.bid > ema_buf[0]) ? "ABOVE" : "BELOW";
   double slope = ema_buf[0] - ema_buf[3]; // slope over 3 bars
   string slope_dir = (slope > 0) ? "RISING" : (slope < 0) ? "FALLING" : "FLAT";
   double dist = tick.bid - ema_buf[0];
   double dist_pct = (ema_buf[0] > 0) ? (dist / ema_buf[0]) * 100.0 : 0;

   // Closed bar vs EMA
   string closed_vs_ema = (rates[1].close > ema_buf[1]) ? "ABOVE" : "BELOW";

   string filename = _Symbol + "_ema" + IntegerToString(period) + "_" + TFToString(tf_min) + ".csv";
   int handle = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_COMMON, ',');
   if(handle == INVALID_HANDLE) return;

   WriteStdHeader(handle, "ema", tf_min);
   WriteBarFields(handle, "running", rates[0].open, rates[0].high, rates[0].low, rates[0].close, rates[0].time, rates[0].tick_volume);
   WriteBarFields(handle, "closed",  rates[1].open, rates[1].high, rates[1].low, rates[1].close, rates[1].time, rates[1].tick_volume);

   FileWrite(handle, "running_ema",           DoubleToString(ema_buf[0], _Digits));
   FileWrite(handle, "running_price_vs_ema",  price_vs_ema);
   FileWrite(handle, "running_dist",          DoubleToString(dist, _Digits));
   FileWrite(handle, "running_dist_pct",      DoubleToString(dist_pct, 4));

   FileWrite(handle, "closed_ema",            DoubleToString(ema_buf[1], _Digits));
   FileWrite(handle, "closed_price_vs_ema",   closed_vs_ema);

   FileWrite(handle, "ema_slope",             slope_dir);
   FileWrite(handle, "ema_slope_value",       DoubleToString(slope, _Digits));

   FileWrite(handle, "cfg_period",            IntegerToString(period));
   FileClose(handle);
}

//=====================================================================
//  RSI — compute + write
//=====================================================================
void WriteRSISignal(int idx)
{
   int tf_min = g_rsi_tf[idx];
   int period = g_rsi_period[idx];
   ENUM_TIMEFRAMES tf = MinToTF(tf_min);

   double rsi_buf[];
   ArraySetAsSeries(rsi_buf, true);
   if(CopyBuffer(g_rsi_handle[idx], 0, 0, 4, rsi_buf) < 4) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 0, 2, rates) < 2) return;

   string running_zone = RSIZone(rsi_buf[0]);
   string closed_zone  = RSIZone(rsi_buf[1]);

   // Cross detection on closed bars
   string closed_cross = "NONE";
   if(rsi_buf[2] < 30 && rsi_buf[1] >= 30)       closed_cross = "CROSS_UP_30";
   else if(rsi_buf[2] > 70 && rsi_buf[1] <= 70)   closed_cross = "CROSS_DOWN_70";
   else if(rsi_buf[2] < 52 && rsi_buf[1] >= 52)   closed_cross = "CROSS_UP_52";
   else if(rsi_buf[2] < 50 && rsi_buf[1] >= 50)   closed_cross = "CROSS_UP_50";
   else if(rsi_buf[2] > 50 && rsi_buf[1] <= 50)   closed_cross = "CROSS_DOWN_50";

   string filename = _Symbol + "_rsi" + IntegerToString(period) + "_" + TFToString(tf_min) + ".csv";
   int handle = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_COMMON, ',');
   if(handle == INVALID_HANDLE) return;

   WriteStdHeader(handle, "rsi", tf_min);
   WriteBarFields(handle, "running", rates[0].open, rates[0].high, rates[0].low, rates[0].close, rates[0].time, rates[0].tick_volume);
   WriteBarFields(handle, "closed",  rates[1].open, rates[1].high, rates[1].low, rates[1].close, rates[1].time, rates[1].tick_volume);

   FileWrite(handle, "running_rsi",           DoubleToString(rsi_buf[0], 2));
   FileWrite(handle, "running_zone",          running_zone);
   FileWrite(handle, "closed_rsi",            DoubleToString(rsi_buf[1], 2));
   FileWrite(handle, "closed_zone",           closed_zone);
   FileWrite(handle, "closed_prev_rsi",       DoubleToString(rsi_buf[2], 2));
   FileWrite(handle, "closed_cross",          closed_cross);

   FileWrite(handle, "cfg_period",            IntegerToString(period));
   FileClose(handle);
}

string RSIZone(double val)
{
   if(val >= 80) return "EXTREME_OB";
   if(val >= 70) return "OVERBOUGHT";
   if(val >= 55) return "BULLISH";
   if(val >= 45) return "NEUTRAL";
   if(val >= 30) return "BEARISH";
   if(val >= 20) return "OVERSOLD";
   return "EXTREME_OS";
}

//=====================================================================
//  BOLLINGER BANDS — compute + write
//=====================================================================
void WriteBBSignal(int idx)
{
   int tf_min = g_bb_tf[idx];
   ENUM_TIMEFRAMES tf = MinToTF(tf_min);

   // Buffer 0 = middle, 1 = upper, 2 = lower
   double mid_buf[], upper_buf[], lower_buf[];
   ArraySetAsSeries(mid_buf, true);
   ArraySetAsSeries(upper_buf, true);
   ArraySetAsSeries(lower_buf, true);
   if(CopyBuffer(g_bb_handle[idx], 0, 0, 22, mid_buf) < 22) return;
   if(CopyBuffer(g_bb_handle[idx], 1, 0, 22, upper_buf) < 22) return;
   if(CopyBuffer(g_bb_handle[idx], 2, 0, 22, lower_buf) < 22) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 0, 2, rates) < 2) return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   double bw = upper_buf[0] - lower_buf[0];
   double pct_running = (bw > 0) ? (tick.bid - lower_buf[0]) / bw * 100.0 : 50.0;

   // Closed bar analysis
   double cls_bw = upper_buf[1] - lower_buf[1];
   double pct_closed = (cls_bw > 0) ? (rates[1].close - lower_buf[1]) / cls_bw * 100.0 : 50.0;

   bool running_above_upper = (tick.bid > upper_buf[0]);
   bool running_below_lower = (tick.bid < lower_buf[0]);
   bool closed_above_upper  = (rates[1].close > upper_buf[1]);
   bool closed_below_lower  = (rates[1].close < lower_buf[1]);

   // Previous bar was outside, current bar came back inside
   bool closed_reenter_from_below = (rates[1].close > lower_buf[1]) && (rates[1].open < lower_buf[1]);
   bool closed_reenter_from_above = (rates[1].close < upper_buf[1]) && (rates[1].open > upper_buf[1]);

   string filename = _Symbol + "_bb" + IntegerToString(g_bb_period[idx]) + "d" + IntegerToString((int)g_bb_deviation[idx]) + "_" + TFToString(tf_min) + ".csv";
   int handle = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_COMMON, ',');
   if(handle == INVALID_HANDLE) return;

   WriteStdHeader(handle, "bb", tf_min);
   WriteBarFields(handle, "running", rates[0].open, rates[0].high, rates[0].low, rates[0].close, rates[0].time, rates[0].tick_volume);
   WriteBarFields(handle, "closed",  rates[1].open, rates[1].high, rates[1].low, rates[1].close, rates[1].time, rates[1].tick_volume);

   FileWrite(handle, "upper_band",              DoubleToString(upper_buf[0], _Digits));
   FileWrite(handle, "middle_band",             DoubleToString(mid_buf[0], _Digits));
   FileWrite(handle, "lower_band",              DoubleToString(lower_buf[0], _Digits));
   FileWrite(handle, "band_width",              DoubleToString(bw, _Digits));

   FileWrite(handle, "running_pct_in_band",     DoubleToString(pct_running, 1));
   FileWrite(handle, "running_above_upper",     running_above_upper ? "TRUE" : "FALSE");
   FileWrite(handle, "running_below_lower",     running_below_lower ? "TRUE" : "FALSE");

   FileWrite(handle, "closed_pct_in_band",      DoubleToString(pct_closed, 1));
   FileWrite(handle, "closed_above_upper",      closed_above_upper ? "TRUE" : "FALSE");
   FileWrite(handle, "closed_below_lower",      closed_below_lower ? "TRUE" : "FALSE");
   FileWrite(handle, "closed_reenter_from_below", closed_reenter_from_below ? "TRUE" : "FALSE");
   FileWrite(handle, "closed_reenter_from_above", closed_reenter_from_above ? "TRUE" : "FALSE");

   // Bandwidth = (upper - lower) / middle × 100 (normalized %)
   // Compute SMA of bandwidth over last 20 closed bars for squeeze detection
   double bandwidth = (mid_buf[0] > 0) ? (bw / mid_buf[0]) * 100.0 : 0;
   double bw_sma = 0;
   for(int i = 1; i <= 20; i++)
   {
      double bw_i = upper_buf[i] - lower_buf[i];
      double mid_i = mid_buf[i];
      if(mid_i > 0) bw_sma += (bw_i / mid_i) * 100.0;
   }
   bw_sma /= 20.0;
   double bw_ratio = (bw_sma > 0) ? bandwidth / bw_sma : 1.0;
   bool bb_squeeze = (bw_ratio < 0.85);

   FileWrite(handle, "bb_bandwidth",            DoubleToString(bandwidth, 4));
   FileWrite(handle, "bb_bandwidth_sma20",      DoubleToString(bw_sma, 4));
   FileWrite(handle, "bb_bandwidth_ratio",      DoubleToString(bw_ratio, 2));
   FileWrite(handle, "bb_squeeze",              bb_squeeze ? "TRUE" : "FALSE");

   FileWrite(handle, "cfg_period",              IntegerToString(g_bb_period[idx]));
   FileWrite(handle, "cfg_deviation",           DoubleToString(g_bb_deviation[idx], 1));
   FileClose(handle);
}

//=====================================================================
//  ADX — compute + write
//=====================================================================
void WriteADXSignal(int idx)
{
   int tf_min = g_adx_tf[idx];
   ENUM_TIMEFRAMES tf = MinToTF(tf_min);

   // Buffer 0 = ADX main, 1 = +DI, 2 = -DI
   double adx_buf[], pdi_buf[], mdi_buf[];
   ArraySetAsSeries(adx_buf, true);
   ArraySetAsSeries(pdi_buf, true);
   ArraySetAsSeries(mdi_buf, true);
   if(CopyBuffer(g_adx_handle[idx], 0, 0, 4, adx_buf) < 4) return;
   if(CopyBuffer(g_adx_handle[idx], 1, 0, 4, pdi_buf) < 4) return;
   if(CopyBuffer(g_adx_handle[idx], 2, 0, 4, mdi_buf) < 4) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 0, 2, rates) < 2) return;

   string trend_strength;
   if(adx_buf[1] < 18)      trend_strength = "RANGING";
   else if(adx_buf[1] < 25) trend_strength = "WEAK_TREND";
   else if(adx_buf[1] < 40) trend_strength = "TRENDING";
   else                      trend_strength = "STRONG_TREND";

   bool adx_rising = (adx_buf[1] > adx_buf[2]) && (adx_buf[2] > adx_buf[3]);
   string di_bias = (pdi_buf[1] > mdi_buf[1]) ? "BULLISH" : "BEARISH";

   string filename = _Symbol + "_adx" + IntegerToString(g_adx_period[idx]) + "_" + TFToString(tf_min) + ".csv";
   int handle = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_COMMON, ',');
   if(handle == INVALID_HANDLE) return;

   WriteStdHeader(handle, "adx", tf_min);
   WriteBarFields(handle, "running", rates[0].open, rates[0].high, rates[0].low, rates[0].close, rates[0].time, rates[0].tick_volume);
   WriteBarFields(handle, "closed",  rates[1].open, rates[1].high, rates[1].low, rates[1].close, rates[1].time, rates[1].tick_volume);

   FileWrite(handle, "running_adx",            DoubleToString(adx_buf[0], 2));
   FileWrite(handle, "running_plus_di",        DoubleToString(pdi_buf[0], 2));
   FileWrite(handle, "running_minus_di",       DoubleToString(mdi_buf[0], 2));

   FileWrite(handle, "closed_adx",             DoubleToString(adx_buf[1], 2));
   FileWrite(handle, "closed_plus_di",         DoubleToString(pdi_buf[1], 2));
   FileWrite(handle, "closed_minus_di",        DoubleToString(mdi_buf[1], 2));
   FileWrite(handle, "closed_trend_strength",  trend_strength);
   FileWrite(handle, "closed_adx_rising",      adx_rising ? "TRUE" : "FALSE");
   FileWrite(handle, "closed_di_bias",         di_bias);

   FileWrite(handle, "cfg_period",             IntegerToString(g_adx_period[idx]));
   FileClose(handle);
}

//=====================================================================
//  MACD — compute + write
//=====================================================================
void WriteMACDSignal(int idx)
{
   int tf_min = g_macd_tf[idx];
   ENUM_TIMEFRAMES tf = MinToTF(tf_min);

   // Buffer 0 = MACD main, 1 = signal line
   double macd_buf[], sig_buf[];
   ArraySetAsSeries(macd_buf, true);
   ArraySetAsSeries(sig_buf, true);
   if(CopyBuffer(g_macd_handle[idx], 0, 0, 4, macd_buf) < 4) return;
   if(CopyBuffer(g_macd_handle[idx], 1, 0, 4, sig_buf) < 4) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 0, 2, rates) < 2) return;

   double running_hist = macd_buf[0] - sig_buf[0];
   double closed_hist  = macd_buf[1] - sig_buf[1];
   double prev_hist    = macd_buf[2] - sig_buf[2];

   // Histogram flip detection on closed bar
   string hist_cross = "NONE";
   if(prev_hist <= 0 && closed_hist > 0) hist_cross = "BULLISH_FLIP";
   if(prev_hist >= 0 && closed_hist < 0) hist_cross = "BEARISH_FLIP";

   // Zero line cross
   string zero_cross = "NONE";
   if(macd_buf[2] <= 0 && macd_buf[1] > 0) zero_cross = "CROSS_ABOVE";
   if(macd_buf[2] >= 0 && macd_buf[1] < 0) zero_cross = "CROSS_BELOW";

   string filename = _Symbol + "_macd" + IntegerToString(g_macd_fast[idx]) + "_" + IntegerToString(g_macd_slow[idx]) + "_" + IntegerToString(g_macd_signal[idx]) + "_" + TFToString(tf_min) + ".csv";
   int handle = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_COMMON, ',');
   if(handle == INVALID_HANDLE) return;

   WriteStdHeader(handle, "macd", tf_min);
   WriteBarFields(handle, "running", rates[0].open, rates[0].high, rates[0].low, rates[0].close, rates[0].time, rates[0].tick_volume);
   WriteBarFields(handle, "closed",  rates[1].open, rates[1].high, rates[1].low, rates[1].close, rates[1].time, rates[1].tick_volume);

   FileWrite(handle, "running_macd",           DoubleToString(macd_buf[0], _Digits));
   FileWrite(handle, "running_signal",         DoubleToString(sig_buf[0], _Digits));
   FileWrite(handle, "running_histogram",      DoubleToString(running_hist, _Digits));

   FileWrite(handle, "closed_macd",            DoubleToString(macd_buf[1], _Digits));
   FileWrite(handle, "closed_signal",          DoubleToString(sig_buf[1], _Digits));
   FileWrite(handle, "closed_histogram",       DoubleToString(closed_hist, _Digits));
   FileWrite(handle, "closed_hist_cross",      hist_cross);
   FileWrite(handle, "closed_zero_cross",      zero_cross);

   FileWrite(handle, "cfg_fast",               IntegerToString(g_macd_fast[idx]));
   FileWrite(handle, "cfg_slow",               IntegerToString(g_macd_slow[idx]));
   FileWrite(handle, "cfg_signal",             IntegerToString(g_macd_signal[idx]));
   FileClose(handle);
}

//=====================================================================
//  STOCHASTIC — compute + write
//=====================================================================
void WriteStochSignal(int idx)
{
   int tf_min = g_stoch_tf[idx];
   ENUM_TIMEFRAMES tf = MinToTF(tf_min);

   // Buffer 0 = %K main, 1 = %D signal
   double k_buf[], d_buf[];
   ArraySetAsSeries(k_buf, true);
   ArraySetAsSeries(d_buf, true);
   if(CopyBuffer(g_stoch_handle[idx], 0, 0, 4, k_buf) < 4) return;
   if(CopyBuffer(g_stoch_handle[idx], 1, 0, 4, d_buf) < 4) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 0, 2, rates) < 2) return;

   string closed_zone = StochZone(k_buf[1]);

   // Cross detection on closed bars
   string closed_cross = "NONE";
   if(k_buf[2] <= d_buf[2] && k_buf[1] > d_buf[1])
   {
      if(k_buf[1] < 25) closed_cross = "BULLISH_OS";     // K crosses above D below 25
      else               closed_cross = "BULLISH";
   }
   else if(k_buf[2] >= d_buf[2] && k_buf[1] < d_buf[1])
   {
      if(k_buf[1] > 75) closed_cross = "BEARISH_OB";     // K crosses below D above 75
      else               closed_cross = "BEARISH";
   }

   string filename = _Symbol + "_stoch" + IntegerToString(g_stoch_k[idx]) + "_" + IntegerToString(g_stoch_d[idx]) + "_" + IntegerToString(g_stoch_slowing[idx]) + "_" + TFToString(tf_min) + ".csv";
   int handle = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_COMMON, ',');
   if(handle == INVALID_HANDLE) return;

   WriteStdHeader(handle, "stoch", tf_min);
   WriteBarFields(handle, "running", rates[0].open, rates[0].high, rates[0].low, rates[0].close, rates[0].time, rates[0].tick_volume);
   WriteBarFields(handle, "closed",  rates[1].open, rates[1].high, rates[1].low, rates[1].close, rates[1].time, rates[1].tick_volume);

   FileWrite(handle, "running_k",              DoubleToString(k_buf[0], 2));
   FileWrite(handle, "running_d",              DoubleToString(d_buf[0], 2));

   FileWrite(handle, "closed_k",               DoubleToString(k_buf[1], 2));
   FileWrite(handle, "closed_d",               DoubleToString(d_buf[1], 2));
   FileWrite(handle, "closed_zone",            closed_zone);
   FileWrite(handle, "closed_cross",           closed_cross);

   FileWrite(handle, "cfg_k_period",           IntegerToString(g_stoch_k[idx]));
   FileWrite(handle, "cfg_d_period",           IntegerToString(g_stoch_d[idx]));
   FileWrite(handle, "cfg_slowing",            IntegerToString(g_stoch_slowing[idx]));
   FileClose(handle);
}

string StochZone(double k)
{
   if(k >= 80) return "OVERBOUGHT";
   if(k <= 20) return "OVERSOLD";
   return "NEUTRAL";
}

//=====================================================================
//  ATR (standalone) — compute + write
//=====================================================================
void WriteATRSignal(int idx)
{
   int tf_min = g_atr_tf[idx];
   ENUM_TIMEFRAMES tf = MinToTF(tf_min);

   double atr_buf[];
   ArraySetAsSeries(atr_buf, true);
   if(CopyBuffer(g_atr_handle[idx], 0, 0, 22, atr_buf) < 22) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 0, 2, rates) < 2) return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   // SMA of ATR over 20 bars for expansion/contraction detection
   double atr_sma = 0;
   for(int i = 1; i <= 20; i++) atr_sma += atr_buf[i];
   atr_sma /= 20.0;

   double ratio = (atr_sma > 0) ? atr_buf[0] / atr_sma : 1.0;
   string vol_state;
   if(ratio > 1.2)      vol_state = "EXPANDING";
   else if(ratio > 1.0) vol_state = "ABOVE_AVG";
   else if(ratio > 0.8) vol_state = "BELOW_AVG";
   else                  vol_state = "CONTRACTING";

   // ATR as % of price
   double atr_pct = (tick.bid > 0) ? (atr_buf[0] / tick.bid) * 100.0 : 0;

   string filename = _Symbol + "_atr" + IntegerToString(g_atr_period[idx]) + "_" + TFToString(tf_min) + ".csv";
   int handle = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_COMMON, ',');
   if(handle == INVALID_HANDLE) return;

   WriteStdHeader(handle, "atr", tf_min);
   WriteBarFields(handle, "running", rates[0].open, rates[0].high, rates[0].low, rates[0].close, rates[0].time, rates[0].tick_volume);
   WriteBarFields(handle, "closed",  rates[1].open, rates[1].high, rates[1].low, rates[1].close, rates[1].time, rates[1].tick_volume);

   FileWrite(handle, "running_atr",            DoubleToString(atr_buf[0], _Digits));
   FileWrite(handle, "running_atr_pct",        DoubleToString(atr_pct, 4));
   FileWrite(handle, "closed_atr",             DoubleToString(atr_buf[1], _Digits));
   FileWrite(handle, "atr_sma20",              DoubleToString(atr_sma, _Digits));
   FileWrite(handle, "atr_vs_sma_ratio",       DoubleToString(ratio, 2));
   FileWrite(handle, "volatility_state",       vol_state);

   FileWrite(handle, "cfg_period",             IntegerToString(g_atr_period[idx]));
   FileClose(handle);
}

//=====================================================================
//  VWAP (Session) — compute + write
//=====================================================================
// Session VWAP resets at 00:00 server time each day.
// Formula: VWAP = Σ(typical_price × volume) / Σ(volume)
// typical_price = (High + Low + Close) / 3
// We compute on M1 bars from session start to current bar, then write
// at the requested output timeframe.
void WriteVWAPSignal(int idx)
{
   int tf_min = g_vwap_tf[idx];
   ENUM_TIMEFRAMES tf = MinToTF(tf_min);

   // Determine today's session start (00:00 server time)
   MqlDateTime dt;
   TimeCurrent(dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime session_start = StructToTime(dt);

   // Count M1 bars from session start to now
   int bars_since_start = Bars(_Symbol, PERIOD_M1, session_start, TimeCurrent());
   if(bars_since_start < 2) return;

   // Cap to prevent excessive computation
   int bars_to_copy = MathMin(bars_since_start, 1500);

   // Copy M1 OHLCV for VWAP computation (non-series: [0]=oldest from session)
   MqlRates m1_rates[];
   ArraySetAsSeries(m1_rates, false);
   int copied = CopyRates(_Symbol, PERIOD_M1, 0, bars_to_copy, m1_rates);
   if(copied < 2) return;

   // Find the first bar at or after session_start
   int session_idx = -1;
   for(int i = 0; i < copied; i++)
   {
      if(m1_rates[i].time >= session_start)
      {
         session_idx = i;
         break;
      }
   }
   if(session_idx < 0 || session_idx >= copied - 1) return;

   // Compute cumulative VWAP from session start
   double cum_tp_vol = 0;
   double cum_vol = 0;
   double vwap = 0;

   for(int i = session_idx; i < copied; i++)
   {
      double typical = (m1_rates[i].high + m1_rates[i].low + m1_rates[i].close) / 3.0;
      double vol = (double)m1_rates[i].tick_volume;
      if(vol <= 0) vol = 1;  // avoid zero volume bars
      cum_tp_vol += typical * vol;
      cum_vol    += vol;
   }

   if(cum_vol <= 0) return;
   vwap = cum_tp_vol / cum_vol;

   // Get running + closed bars at the requested TF
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, tf, 0, 2, rates) < 2) return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   // Price vs VWAP
   string price_vs_vwap = (tick.bid > vwap) ? "ABOVE" : "BELOW";
   double dist = tick.bid - vwap;
   double dist_pct = (vwap > 0) ? (dist / vwap) * 100.0 : 0;

   // Closed bar vs VWAP
   string closed_vs_vwap = (rates[1].close > vwap) ? "ABOVE" : "BELOW";
   double closed_dist = rates[1].close - vwap;

   // Session bar count (how far into session we are)
   int session_bars = copied - session_idx;

   string filename = _Symbol + "_vwap_" + TFToString(tf_min) + ".csv";
   int handle = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_COMMON, ',');
   if(handle == INVALID_HANDLE) return;

   WriteStdHeader(handle, "vwap", tf_min);
   WriteBarFields(handle, "running", rates[0].open, rates[0].high, rates[0].low, rates[0].close, rates[0].time, rates[0].tick_volume);
   WriteBarFields(handle, "closed",  rates[1].open, rates[1].high, rates[1].low, rates[1].close, rates[1].time, rates[1].tick_volume);

   FileWrite(handle, "vwap",                   DoubleToString(vwap, _Digits));
   FileWrite(handle, "running_price_vs_vwap",  price_vs_vwap);
   FileWrite(handle, "running_dist_to_vwap",   DoubleToString(dist, _Digits));
   FileWrite(handle, "running_dist_pct",       DoubleToString(dist_pct, 4));
   FileWrite(handle, "closed_price_vs_vwap",   closed_vs_vwap);
   FileWrite(handle, "closed_dist_to_vwap",    DoubleToString(closed_dist, _Digits));
   FileWrite(handle, "session_m1_bars",        IntegerToString(session_bars));
   FileWrite(handle, "cum_volume",             DoubleToString(cum_vol, 0));

   FileClose(handle);
}

//=====================================================================
//  CANDLE ANALYSIS  — comprehensive candle property writer
//=====================================================================
// Helper: compute candle fields for a single bar and write to CSV
void WriteCandleBarFields(int handle, string prefix,
                          double open, double high, double low, double close)
{
   double body_top    = MathMax(open, close);
   double body_bottom = MathMin(open, close);
   double body_size   = body_top - body_bottom;
   double upper_wick  = high - body_top;
   double lower_wick  = body_bottom - low;
   double total_range = high - low;

   // Prevent division by zero
   double range_safe = (total_range > _Point) ? total_range : _Point;
   double body_safe  = (body_size   > _Point) ? body_size   : _Point;

   // Percentages (of total range)
   double body_pct       = (body_size / range_safe) * 100.0;
   double upper_wick_pct = (upper_wick / range_safe) * 100.0;
   double lower_wick_pct = (lower_wick / range_safe) * 100.0;

   // Ratios (wick / body) — 0.0 if doji
   double upper_wick_ratio = (body_size > _Point) ? (upper_wick / body_safe) : 0.0;
   double lower_wick_ratio = (body_size > _Point) ? (lower_wick / body_safe) : 0.0;

   // Direction
   string candle_dir = "DOJI";
   if(close > open)       candle_dir = "UP";
   else if(close < open)  candle_dir = "DOWN";

   // Boolean flags
   bool has_long_upper = (upper_wick >= 2.0 * body_safe) && (total_range > _Point);
   bool has_long_lower = (lower_wick >= 2.0 * body_safe) && (total_range > _Point);
   bool is_bullish     = (close > open);
   bool is_bearish     = (close < open);

   // Candle type classification
   //   MARUBOZU:       body > 80% of range (strong move, tiny wicks)
   //   DOJI:           body < 10% of range
   //   HAMMER:         lower_wick >= 2x body AND upper_wick < body (bullish reversal)
   //   SHOOTING_STAR:  upper_wick >= 2x body AND lower_wick < body (bearish reversal)
   //   SPINNING_TOP:   body 10-40% of range, both wicks significant
   //   NORMAL:         everything else
   string candle_type = "NORMAL";
   if(total_range <= _Point)
      candle_type = "DOJI";
   else if(body_pct >= 80.0)
      candle_type = "MARUBOZU";
   else if(body_pct < 10.0)
      candle_type = "DOJI";
   else if(lower_wick >= 2.0 * body_safe && upper_wick < body_safe)
      candle_type = "HAMMER";
   else if(upper_wick >= 2.0 * body_safe && lower_wick < body_safe)
      candle_type = "SHOOTING_STAR";
   else if(body_pct < 40.0 && upper_wick > 0.5 * body_safe && lower_wick > 0.5 * body_safe)
      candle_type = "SPINNING_TOP";

   // Write all fields
   FileWrite(handle, prefix + "_body_size",         DoubleToString(body_size, _Digits));
   FileWrite(handle, prefix + "_upper_wick_size",   DoubleToString(upper_wick, _Digits));
   FileWrite(handle, prefix + "_lower_wick_size",   DoubleToString(lower_wick, _Digits));
   FileWrite(handle, prefix + "_total_range",       DoubleToString(total_range, _Digits));
   FileWrite(handle, prefix + "_body_pct",          DoubleToString(body_pct, 1));
   FileWrite(handle, prefix + "_upper_wick_pct",    DoubleToString(upper_wick_pct, 1));
   FileWrite(handle, prefix + "_lower_wick_pct",    DoubleToString(lower_wick_pct, 1));
   FileWrite(handle, prefix + "_upper_wick_ratio",  DoubleToString(upper_wick_ratio, 2));
   FileWrite(handle, prefix + "_lower_wick_ratio",  DoubleToString(lower_wick_ratio, 2));
   FileWrite(handle, prefix + "_candle_dir",        candle_dir);
   FileWrite(handle, prefix + "_candle_type",       candle_type);
   FileWrite(handle, prefix + "_has_long_upper",    has_long_upper ? "TRUE" : "FALSE");
   FileWrite(handle, prefix + "_has_long_lower",    has_long_lower ? "TRUE" : "FALSE");
   FileWrite(handle, prefix + "_is_bullish",        is_bullish ? "TRUE" : "FALSE");
   FileWrite(handle, prefix + "_is_bearish",        is_bearish ? "TRUE" : "FALSE");
}

void WriteCandleSignal(int idx)
{
   int tf_min = g_candle_tf[idx];
   ENUM_TIMEFRAMES tf = MinToTF(tf_min);

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   double opens[], highs[], lows[], closes[];
   long   volumes[];
   datetime times[];

   if(!IsNativeTF(tf_min))
   {
      // Synthetic TF (e.g. M45)
      int total = BuildSyntheticBars(tf_min, 3, opens, highs, lows, closes, volumes, times);
      if(total < 2) return;

      int run = total - 1;  // running bar (current)
      int cls = total - 2;  // last closed bar

      string filename = _Symbol + "_candle_" + TFToString(tf_min) + ".csv";
      int handle = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_COMMON, ',');
      if(handle == INVALID_HANDLE) return;

      WriteStdHeader(handle, "candle", tf_min);
      WriteBarFields(handle, "running", opens[run], highs[run], lows[run], closes[run], times[run], volumes[run]);
      WriteBarFields(handle, "closed",  opens[cls], highs[cls], lows[cls], closes[cls], times[cls], volumes[cls]);

      WriteCandleBarFields(handle, "running", opens[run], highs[run], lows[run], closes[run]);
      WriteCandleBarFields(handle, "closed",  opens[cls], highs[cls], lows[cls], closes[cls]);

      FileClose(handle);
   }
   else
   {
      // Native TF
      MqlRates rates[];
      ArraySetAsSeries(rates, true);
      if(CopyRates(_Symbol, tf, 0, 2, rates) < 2) return;

      string filename = _Symbol + "_candle_" + TFToString(tf_min) + ".csv";
      int handle = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_COMMON, ',');
      if(handle == INVALID_HANDLE) return;

      WriteStdHeader(handle, "candle", tf_min);
      WriteBarFields(handle, "running", rates[0].open, rates[0].high, rates[0].low, rates[0].close, rates[0].time, rates[0].tick_volume);
      WriteBarFields(handle, "closed",  rates[1].open, rates[1].high, rates[1].low, rates[1].close, rates[1].time, rates[1].tick_volume);

      WriteCandleBarFields(handle, "running", rates[0].open, rates[0].high, rates[0].low, rates[0].close);
      WriteCandleBarFields(handle, "closed",  rates[1].open, rates[1].high, rates[1].low, rates[1].close);

      FileClose(handle);
   }
}
//+------------------------------------------------------------------+
