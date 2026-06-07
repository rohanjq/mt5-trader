//+------------------------------------------------------------------+
//| DC_Channels.mq5 - Donchian Channel signal writer                  |
//| Attach to ANY symbol — writes CSV as dc_channels_<SYMBOL>.csv     |
//| Place in: MetaTrader5-Docker/data/experts/ (auto-compiled)        |
//+------------------------------------------------------------------+
#property copyright "mt5-trader"
#property version   "1.00"
#property strict

//--- Input parameters (configurable per chart)
input int    InpLength     = 20;       // DC length (number of bars)
input int    InpOffset     = 0;        // DC offset
input int    InpTimeframe  = 45;       // Timeframe in minutes (45 = 45min DC)
input string InpSignalDir  = "signals"; // Subfolder under MQL5/Files

//--- Global variables
int      g_timer_seconds = 5;

//+------------------------------------------------------------------+
//| Expert initialization                                             |
//+------------------------------------------------------------------+
int OnInit()
{
   EventSetTimer(g_timer_seconds);
   Print("DC_Channels EA initialized: Symbol=", _Symbol,
         " Length=", InpLength, " Offset=", InpOffset,
         " TF=", InpTimeframe, "min");
   WriteSignals();
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
}

//+------------------------------------------------------------------+
//| Timer event — write signals periodically                          |
//+------------------------------------------------------------------+
void OnTimer()
{
   WriteSignals();
}

//+------------------------------------------------------------------+
//| Tick event                                                        |
//+------------------------------------------------------------------+
void OnTick()
{
   WriteSignals();
}

//+------------------------------------------------------------------+
//| Map minutes to ENUM_TIMEFRAMES                                    |
//+------------------------------------------------------------------+
ENUM_TIMEFRAMES MinutesToTimeframe(int minutes)
{
   switch(minutes)
   {
      case 1:    return PERIOD_M1;
      case 2:    return PERIOD_M2;
      case 3:    return PERIOD_M3;
      case 4:    return PERIOD_M4;
      case 5:    return PERIOD_M5;
      case 6:    return PERIOD_M6;
      case 10:   return PERIOD_M10;
      case 12:   return PERIOD_M12;
      case 15:   return PERIOD_M15;
      case 20:   return PERIOD_M20;
      case 30:   return PERIOD_M30;
      case 45:   return PERIOD_M30;  // Will use M30 bars and compute manually
      case 60:   return PERIOD_H1;
      case 120:  return PERIOD_H2;
      case 180:  return PERIOD_H3;
      case 240:  return PERIOD_H4;
      case 360:  return PERIOD_H6;
      case 480:  return PERIOD_H8;
      case 720:  return PERIOD_H12;
      case 1440: return PERIOD_D1;
      default:   return PERIOD_M1;
   }
}

//+------------------------------------------------------------------+
//| Check if timeframe is native MT5 or needs synthetic computation   |
//+------------------------------------------------------------------+
bool IsNativeTimeframe(int minutes)
{
   int native[] = {1,2,3,4,5,6,10,12,15,20,30,60,120,180,240,360,480,720,1440};
   for(int i = 0; i < ArraySize(native); i++)
      if(native[i] == minutes) return true;
   return false;
}

//+------------------------------------------------------------------+
//| Compute Donchian Channel and write CSV                            |
//+------------------------------------------------------------------+
void WriteSignals()
{
   double upper_band = 0, lower_band = 0, mid_band = 0;
   bool ok = false;

   if(IsNativeTimeframe(InpTimeframe))
   {
      ok = ComputeDCNative(upper_band, lower_band, mid_band);
   }
   else
   {
      ok = ComputeDCSynthetic(upper_band, lower_band, mid_band);
   }

   if(!ok)
   {
      Print("DC_Channels: Failed to compute Donchian Channel");
      return;
   }

   //--- Current price info
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   double bid = tick.bid;
   double ask = tick.ask;

   //--- Determine channel position and wick detection
   double channel_width = upper_band - lower_band;
   string price_zone = "MIDDLE";
   double pct_in_channel = 0;

   if(channel_width > 0)
      pct_in_channel = (bid - lower_band) / channel_width * 100.0;

   if(pct_in_channel >= 90)      price_zone = "UPPER";
   else if(pct_in_channel <= 10) price_zone = "LOWER";
   else if(pct_in_channel >= 70) price_zone = "UPPER_MID";
   else if(pct_in_channel <= 30) price_zone = "LOWER_MID";

   //--- Wick detection: check last closed bar on M1
   double last_high  = iHigh(_Symbol, PERIOD_M1, 1);
   double last_low   = iLow(_Symbol, PERIOD_M1, 1);
   double last_open  = iOpen(_Symbol, PERIOD_M1, 1);
   double last_close = iClose(_Symbol, PERIOD_M1, 1);

   bool touched_upper = (last_high >= upper_band);
   bool touched_lower = (last_low <= lower_band);

   //--- Wick rejection detection
   //  Upper wick rejection: touched upper band but closed below it with upper wick
   double body_top    = MathMax(last_open, last_close);
   double body_bottom = MathMin(last_open, last_close);
   double upper_wick  = last_high - body_top;
   double lower_wick  = body_bottom - last_low;
   double body_size   = body_top - body_bottom;

   bool upper_wick_rejection = touched_upper && (upper_wick > body_size) && (last_close < upper_band);
   bool lower_wick_rejection = touched_lower && (lower_wick > body_size) && (last_close > lower_band);

   //--- Write CSV
   string filename = InpSignalDir + "\\dc_channels_" + _Symbol + ".csv";
   int handle = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');

   if(handle == INVALID_HANDLE)
   {
      Print("DC_Channels: Cannot open file ", filename, " Error: ", GetLastError());
      return;
   }

   FileWrite(handle, "key", "value");
   FileWrite(handle, "upper_band",          DoubleToString(upper_band, 2));
   FileWrite(handle, "lower_band",          DoubleToString(lower_band, 2));
   FileWrite(handle, "mid_band",            DoubleToString(mid_band, 2));
   FileWrite(handle, "channel_width",       DoubleToString(channel_width, 2));
   FileWrite(handle, "bid",                 DoubleToString(bid, 2));
   FileWrite(handle, "ask",                 DoubleToString(ask, 2));
   FileWrite(handle, "price_zone",          price_zone);
   FileWrite(handle, "pct_in_channel",      DoubleToString(pct_in_channel, 1));
   FileWrite(handle, "touched_upper",       touched_upper ? "TRUE" : "FALSE");
   FileWrite(handle, "touched_lower",       touched_lower ? "TRUE" : "FALSE");
   FileWrite(handle, "upper_wick_rejection", upper_wick_rejection ? "TRUE" : "FALSE");
   FileWrite(handle, "lower_wick_rejection", lower_wick_rejection ? "TRUE" : "FALSE");
   FileWrite(handle, "upper_wick_size",     DoubleToString(upper_wick, 2));
   FileWrite(handle, "lower_wick_size",     DoubleToString(lower_wick, 2));
   FileWrite(handle, "body_size",           DoubleToString(body_size, 2));
   FileWrite(handle, "dc_length",           IntegerToString(InpLength));
   FileWrite(handle, "dc_offset",           IntegerToString(InpOffset));
   FileWrite(handle, "dc_timeframe_min",    IntegerToString(InpTimeframe));

   FileClose(handle);
}

//+------------------------------------------------------------------+
//| Compute DC from native MT5 timeframe bars                         |
//+------------------------------------------------------------------+
bool ComputeDCNative(double &upper, double &lower, double &mid)
{
   ENUM_TIMEFRAMES tf = MinutesToTimeframe(InpTimeframe);
   int bars_needed = InpLength + InpOffset + 1;

   double highs[], lows[];
   ArraySetAsSeries(highs, true);
   ArraySetAsSeries(lows, true);

   if(CopyHigh(_Symbol, tf, InpOffset + 1, InpLength, highs) < InpLength) return false;
   if(CopyLow(_Symbol, tf, InpOffset + 1, InpLength, lows) < InpLength) return false;

   upper = highs[ArrayMaximum(highs)];
   lower = lows[ArrayMinimum(lows)];
   mid = (upper + lower) / 2.0;

   return true;
}

//+------------------------------------------------------------------+
//| Compute DC from M1 bars for non-native timeframes (e.g. 45min)    |
//+------------------------------------------------------------------+
bool ComputeDCSynthetic(double &upper, double &lower, double &mid)
{
   //--- For 45min with length 20: need 20 synthetic bars of 45 M1 candles each
   int m1_per_bar = InpTimeframe;
   int total_m1 = InpLength * m1_per_bar;
   int offset_m1 = InpOffset * m1_per_bar;

   double highs[], lows[];
   ArraySetAsSeries(highs, true);
   ArraySetAsSeries(lows, true);

   if(CopyHigh(_Symbol, PERIOD_M1, offset_m1 + 1, total_m1, highs) < total_m1) return false;
   if(CopyLow(_Symbol, PERIOD_M1, offset_m1 + 1, total_m1, lows) < total_m1) return false;

   //--- Find highest high and lowest low across all M1 bars in the lookback
   upper = highs[ArrayMaximum(highs)];
   lower = lows[ArrayMinimum(lows)];
   mid = (upper + lower) / 2.0;

   return true;
}
//+------------------------------------------------------------------+
