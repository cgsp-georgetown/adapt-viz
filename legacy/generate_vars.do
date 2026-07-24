/* 
This file merges together county-level variables, and accounts for county code changes in the intervening years (1991-2022).
It saves the county-level variables merged so it is ready for index-level estimates.

Last updated JKA 2.27.26
*/
//
// local maindir "/Users/ameliabloomfield/Desktop/ADI-variables-for-index/county_level"
// local dtadir "/Users/ameliabloomfield/Desktop/Manufacturing-Trade-Exposure-Analysis/dta"
local maindir "C:\Users\ja1644\Documents\GitHub\ADI-variables-for-index\county_level"
local dtadir "C:\Users\ja1644\Documents\GitHub\Manufacturing-Trade-Exposure-Analysis\dta"
local regdir "C:\Users\ja1644\Documents\GitHub\Manufacturing-Trade-Exposure-Analysis\CZone_Regression\czone_STARs_1991_2022"
local servdir "C:\Users\ja1644\Documents\GitHub\Services-Analysis\Local Shocks\clean"
local stardir "C:\Users\ja1644\Documents\GitHub\ADI-variables-for-index\Opportunity@Work\STARs_all_counties" 
local savedir "C:\Users\ja1644\Documents\GitHub\adapt_test_viz"
local collegedta "C:\Users\ja1644\Documents\GitHub\Social-Spending\dta\IPEDS\data\finished\county_panel_90001122.dta"

use "`maindir'/mfgsh_wide.dta", clear

merge 1:1 countyid using "`maindir'/county_name.dta", nogen

merge 1:1 countyid using "`maindir'/2022_inc.dta", nogen

merge 1:1 countyid using "`maindir'/2022_median_2011.dta", nogen

merge 1:1 countyid using "`maindir'/sdf_panel_county_1990_2022.dta", nogen keepusing(totalexp_lessfed_1990 totalexp_lessfed_2022  v33_2022 v33_1990)

merge 1:1 countyid using "`maindir'/educ_merged_real_county.dta", nogen keepusing(educ_pct_total_stloc1992 educ_pct_total_stloc2022)

merge 1:1 countyid using "`maindir'/trade_vars/trade_exposure_vars.dta", nogen

merge 1:1 countyid using "`maindir'/college_emp_rate.dta", nogen keepusing(*2022)

merge 1:1 countyid using "`maindir'/county_total_pop199020112022.dta", nogen keepusing(*2022)


// merge 1:1 countyid using "`maindir'/average_wages_2022.dta", nogen keepusing(*2022)

merge 1:1 countyid using "`regdir'/input/county/pred_employment_manuf_star_county.dta", nogen keepusing(pred_emp_loss total_pred_emp_loss pct_pred_emp_loss pred_emp_gain total_pred_emp_gain pct_pred_emp_gain pct_jobs_rebound pct_jobs_rebound_greater net_job_chng)

merge 1:1 countyid using "`servdir'/estimated_emp_effects_2017_2022_county.dta", nogen keepusing (dservExp_pen_2017_2022 dservImp_pen_2017_2022 exp_emp imp_emp trade_emp)
rename exp_emp tradserv_exp_emp_2017_2022
rename imp_emp tradserv_imp_emp_2017_2022

merge 1:1 countyid using "`maindir'/county_potential_ppupildef_d_star_emp_rate.dta", nogen

* set stars employment rates in 2011 to be 2012 values; 2 LA parishes & Broomfield County, CO with missing 2011 values
merge 1:1 countyid using "`maindir'/average_wages_2022.dta", nogen
rename total_workers_county* total_workers*

drop if countyid > 72000 // drop Puerto Rico

* drop unwanted variables
drop med_wage_star_log2022 med_wage_log2022 d_med_wage_star_log_2011_2022 d_med_wage_log_2011_2022 STAR_emp_rate

* local deflator
rename v33_* num_pupils_*
// deflate from 2022 to 2026
gen ppupil_deflate_2022 = 1.13*(totalexp_lessfed_2022/num_pupils_2022)/(incwage_2022/nationalwage_2022)
// deflate from 1999 to 2026
replace county_median2022 = 1.98*county_median2022
replace star_median2022 = 1.98*star_median2022

* use 2021 populations for 2022
replace total_pop2022 = 956446 if countyid == 9001
replace total_pop2022 = 898636 if countyid == 9003
replace total_pop2022 = 185175 if countyid == 9005
replace total_pop2022 = 164568 if countyid == 9007
replace total_pop2022 = 864751 if countyid == 9009
replace total_pop2022 = 269131 if countyid == 9011
replace total_pop2022 = 150120 if countyid == 9013
replace total_pop2022 = 116503 if countyid == 9015

* copy Manhattan values into other NYC counties
foreach v of varlist educ_pct_total_stloc1992 educ_pct_total_stloc2022 {
    su `v' if countyid==36061
    local manval = r(mean)   // works if one obs per countyid
    replace `v' = `manval' if inlist(countyid,36047,36005,36081,36085)
}

* do county changes
drop if countyid == .
drop if countyid == 50000 // Vermont
drop if countyid == 51515 //Bedford city merges into Bedford County 51019; drop
drop if countyid == 51560 //Clifton Forge merges into Alleghany county (51005); drop
drop if countyid == 51595 //drop Emporia city (missing educ data)
drop if countyid == 51780 // South Boston VA merges into Halifax county (51083) in 1995
drop if countyid == 46017 // drop Buffalo county, SD 
drop if countyid == 25000 // Massachusetts
drop if countyid == 38000 // North Dakota
drop if countyid == 33000 // New Hampshire
drop if countyid == 30113 // Yellowstone National Park
drop if countyid == 20759 // unrecognized
drop if countyid == 20000 // Kansas
drop if countyid == 18000 // Indiana
drop if countyid == 17403 // St. Clair County, Illinois
drop if countyid == 15005 // Kalawao County
drop if countyid == 13000 // Georgia
drop if countyid == 4065  // unrecognized
drop if countyid == 4203 // unrecognized
drop if countyid == 2275 // Wrangell City and Borough, AK (population ~2000)
drop if countyid == 2010 // unrecognized
drop if countyid == 2232 // 
drop if countyid == 02232 // Skagway-Hoonah-Angoon Census Area  (2007) split into   Skagway Municipality: FIPS code 02230 &   Hoonah-Angoon Census Area: FIPS code 02105
drop if countyid == 2230 // Skagway Municipality
drop if countyid == 2198 // Prince of Wales-Hyder Census Area
drop if countyid == 2195 // Petersburg, Alaska
drop if countyid == 2158 // Kusilvak ,Alaska
drop if countyid == 2105 // Hoonah-Angoon
drop if countyid == 2068 // Denali Borough
drop if countyid == 2066 // Copper River Census Area
drop if countyid == 2063 // Chugach Census Area, AK 
replace county_name = "Yakutat City and Borough, Alaska" if countyid == 2282 

* Shannon County (FIPS 46113) is renamed to Oglala Lakota County (FIPS 46102)
replace county_name = "Oglala Lakota County, South Dakota" if countyid == 46113
replace countyid = 46102 if countyid == 46113
replace county_name = "Oglala Lakota County, South Dakota" if countyid == 46102

* 1997: Dade county (FIPS 12025) is renamed as Miami-Dade county (FIPS 12086)
replace county_name = "Miami-Dade County, Florida" if countyid == 12025
replace county_name = "Miami-Dade County, Florida" if countyid == 12086
replace countyid = 12086 if countyid == 12025

/* -----------------------------------------------------------------------
   MERGE DUPLICATE COUNTY ROWS (e.g. 12086, 46102)
   Strategy: within each countyid, keep the first non-missing value
   for every variable across duplicate rows.
----------------------------------------------------------------------- */

/* Step 1 -- tag duplicates */
duplicates tag countyid, gen(dup_tag)

/* Step 2 -- for each variable, carry non-missing values within countyid.
   This loops over all numeric vars; string vars handled separately. */
ds countyid, not                          // get all vars except the ID
local allvars `r(varlist)'

/* Numeric variables: replace missing with non-missing from other row */
foreach v of local allvars {
    cap confirm numeric variable `v'
    if !_rc {
        bysort countyid: replace `v' = `v'[_n-1] if missing(`v') & !missing(`v'[_n-1])
        bysort countyid: replace `v' = `v'[_n+1] if missing(`v') & !missing(`v'[_n+1])
    }
}

/* String variables: same logic */
ds, has(type string)
local strvars `r(varlist)'
foreach v of local strvars {
    bysort countyid: replace `v' = `v'[_n-1] if `v' == "" & `v'[_n-1] != ""
    bysort countyid: replace `v' = `v'[_n+1] if `v' == "" & `v'[_n+1] != ""
}

/* Step 3 -- drop the now-redundant duplicate row, keep first */
bysort countyid: keep if _n == 1

/* Step 4 -- verify */
duplicates report countyid
assert r(unique_value) == r(N)   // will throw error if dupes remain

di "Done. Each countyid now has exactly one row."

*2001: Broomfield county (FIPS 8014) is created out of parts of Adams, Boulder, Jefferson, and Weld counties
replace county_name = "Broomfield County, Colorado" if countyid==8014
* -------------------------------------------------------------
* Fill missing Broomfield County (8014) values
* using weighted average of Adams (8001), Boulder (8013),
* Jefferson (8059), and Weld (8123)
* Population weights based on land taken in 2001
* -------------------------------------------------------------
* Define population weights
local w_adams     = 15870
local w_boulder   = 21512
local w_jefferson = 1726
local w_weld      = 69
local w_total     = `w_adams' + `w_boulder' + `w_jefferson' + `w_weld'

* Identify numeric variables to impute
ds, has(type numeric)
local numvars `r(varlist)'

* Temporary dataset: only the 4 parent counties
preserve
keep if inlist(countyid, 8001, 8013, 8059, 8123)

display "After keep: _N = " _N
if _N == 0 {
    display as error "None of the parent counties (8001, 8013, 8059, 8123) found in data."
    exit
}

gen weight = .
replace weight = `w_adams'     if countyid == 8001
replace weight = `w_boulder'   if countyid == 8013
replace weight = `w_jefferson' if countyid == 8059
replace weight = `w_weld'      if countyid == 8123

* Build numvars safely (only numeric vars you want to average)
ds countyid county_name qpop, not
local numvars `r(varlist)'   // or define manually

* Compute weighted sum for each missing variable
foreach v of local numvars {
    quietly gen double wt_`v' = `v' * weight if !missing(`v')
}

* Collapse to one row of weighted sums
collapse (sum) wt_*, fast

* Check if collapse worked
if _N == 0 {
    display as error "ERROR: Collapse failed — no data after weighting."
    restore
    exit 198
}

* Now safe to create identifiers (original vars are gone)
gen countyid = 8014
gen county_name = "Broomfield County, Colorado"


* Compute weighted averages
foreach v of local numvars {
    capture confirm variable wt_`v'
    if !_rc {
        gen double `v' = wt_`v' / `w_total'
        drop wt_`v'
    }
    else {
        gen `v' = .
    }
}

* Save imputed Broomfield row
tempfile broom_imputed
save `broom_imputed', replace

restore  // ← Now back to full data

* Drop existing Broomfield
drop if countyid == 8014
* Now append the clean imputed row
append using `broom_imputed'
drop weight
* Final cleanup
display as text "Broomfield (8014) successfully imputed with weighted average."

// replaced null for imports as 0 if super small county
replace d_m_usdev82011_2022 = 0 if d_m_usdev82011_2022 == . & total_pop2022 < 1000
replace d_x_uswld_2011_2022 = 0 if d_x_uswld_2011_2022== . & total_pop2022 < 1000

***** CONNECTICUT CODE CHANGES

// rename new CT counties
replace county_name = "Capitol Planning Region, Connecticut" if countyid == 9110
replace county_name = "Greater Bridgeport Planning Region, Connecticut" if countyid == 9120
replace county_name = "Lower Connecticut River Valley Planning Region, Connecticut" if countyid == 9130
replace county_name = "Naugatuck Valley Planning Region, Connecticut" if countyid == 9140
replace county_name = "Northeastern Connecticut Planning Region, Connecticut" if countyid == 9150
replace county_name = "Northwest Hills Planning Region, Connecticut" if countyid == 9160
replace county_name = "South Central Connecticut Planning Region, Connecticut" if countyid == 9170
replace county_name = "Southeastern Connecticut Planning Region, Connecticut" if countyid == 9180
replace county_name = "Western Connecticut Planning Region, Connecticut" if countyid == 9190

* use state-wide CT 2022 values for all counties in CT in most recent year
preserve
keep if countyid > 9000 & countyid < 10000

foreach var in num_pupils_2022 ppupil_deflate_2022 educ_pct_total_stloc2022 employment_rate_2022 star_emp_rate_2022 emp_rate_college2022 county_median2022 star_median2022 d_m_dw_LT_usdev82011_2022 d_m_dw_usdev82011_2022 d_m_up_LT_usdev82011_2022 d_m_up_usdev82011_2022 d_m_usdev82011_2022 d_x_uswld_2011_2022   {

	egen `var'_n = total(`var'*total_pop2022) if countyid < 9100, by(countyid)
	egen `var'_d = total(total_pop2022) if countyid < 9100, by(countyid) 
	local `var'_ct = `var'_n/`var'_d
	replace `var' = ``var'_ct' if countyid > 9100 & countyid < 9200
	drop `var'_n `var'_d
}

tempfile connecticut
save `connecticut', replace
restore
merge m:1 countyid using `connecticut', update replace nogen

* Get only numeric variables
order countyid county_name
ds mfgsh1991-ppupil_deflate_2022, has(type numeric)

local numvars `r(varlist)' 
drop if county_name == ""
collapse (mean) `numvars', by(countyid county_name qpop) // collapse to only one observation per county

* abbreviate state names
* Make sure your variable is string
tostring county_name, replace force
* Extract state name
gen statefips = floor(countyid / 1000)
gen state = ""
replace state = "AL" if statefips == 1
replace state = "AK" if statefips == 2
replace state = "AZ" if statefips == 4
replace state = "AR" if statefips == 5
replace state = "CA" if statefips == 6
replace state = "CO" if statefips == 8
replace state = "CT" if statefips == 9
replace state = "DE" if statefips == 10
replace state = "DC" if statefips == 11
replace state = "FL" if statefips == 12
replace state = "GA" if statefips == 13
replace state = "HI" if statefips == 15
replace state = "ID" if statefips == 16
replace state = "IL" if statefips == 17
replace state = "IN" if statefips == 18
replace state = "IA" if statefips == 19
replace state = "KS" if statefips == 20
replace state = "KY" if statefips == 21
replace state = "LA" if statefips == 22
replace state = "ME" if statefips == 23
replace state = "MD" if statefips == 24
replace state = "MA" if statefips == 25
replace state = "MI" if statefips == 26
replace state = "MN" if statefips == 27
replace state = "MS" if statefips == 28
replace state = "MO" if statefips == 29
replace state = "MT" if statefips == 30
replace state = "NE" if statefips == 31
replace state = "NV" if statefips == 32
replace state = "NH" if statefips == 33
replace state = "NJ" if statefips == 34
replace state = "NM" if statefips == 35
replace state = "NY" if statefips == 36
replace state = "NC" if statefips == 37
replace state = "ND" if statefips == 38
replace state = "OH" if statefips == 39
replace state = "OK" if statefips == 40
replace state = "OR" if statefips == 41
replace state = "PA" if statefips == 42
replace state = "RI" if statefips == 44
replace state = "SC" if statefips == 45
replace state = "SD" if statefips == 46
replace state = "TN" if statefips == 47
replace state = "TX" if statefips == 48
replace state = "UT" if statefips == 49
replace state = "VT" if statefips == 50
replace state = "VA" if statefips == 51
replace state = "WA" if statefips == 53
replace state = "WV" if statefips == 54
replace state = "WI" if statefips == 55
replace state = "WY" if statefips == 56

* Replace full state names with abbreviations
* DC (missing from your original list entirely)
replace county_name = subinstr(county_name, ", District of Columbia", ", DC", .)

replace county_name = subinstr(county_name, ", Alabama", ", AL", .)
replace county_name = subinstr(county_name, ", Alaska", ", AK", .)
replace county_name = subinstr(county_name, ", Arizona", ", AZ", .)
replace county_name = subinstr(county_name, ", Arkansas", ", AR", .)
replace county_name = subinstr(county_name, ", California", ", CA", .)
replace county_name = subinstr(county_name, ", Colorado", ", CO", .)
replace county_name = subinstr(county_name, ", Connecticut", ", CT", .)
replace county_name = subinstr(county_name, ", Delaware", ", DE", .)
replace county_name = subinstr(county_name, ", Florida", ", FL", .)
replace county_name = subinstr(county_name, ", Georgia", ", GA", .)
replace county_name = subinstr(county_name, ", Hawaii", ", HI", .)
replace county_name = subinstr(county_name, ", Idaho", ", ID", .)
replace county_name = subinstr(county_name, ", Illinois", ", IL", .)
replace county_name = subinstr(county_name, ", Indiana", ", IN", .)
replace county_name = subinstr(county_name, ", Iowa", ", IA", .)
replace county_name = subinstr(county_name, ", Kansas", ", KS", .)
replace county_name = subinstr(county_name, ", Kentucky", ", KY", .)
replace county_name = subinstr(county_name, ", Louisiana", ", LA", .)
replace county_name = subinstr(county_name, ", Maine", ", ME", .)
replace county_name = subinstr(county_name, ", Maryland", ", MD", .)
replace county_name = subinstr(county_name, ", Massachusetts", ", MA", .)
replace county_name = subinstr(county_name, ", Michigan", ", MI", .)
replace county_name = subinstr(county_name, ", Minnesota", ", MN", .)
replace county_name = subinstr(county_name, ", Mississippi", ", MS", .)
replace county_name = subinstr(county_name, ", Missouri", ", MO", .)
replace county_name = subinstr(county_name, ", Montana", ", MT", .)
replace county_name = subinstr(county_name, ", Nebraska", ", NE", .)
replace county_name = subinstr(county_name, ", Nevada", ", NV", .)
replace county_name = subinstr(county_name, ", New Hampshire", ", NH", .)
replace county_name = subinstr(county_name, ", New Jersey", ", NJ", .)
replace county_name = subinstr(county_name, ", New Mexico", ", NM", .)
replace county_name = subinstr(county_name, ", New York", ", NY", .)
replace county_name = subinstr(county_name, ", North Carolina", ", NC", .)
replace county_name = subinstr(county_name, ", North Dakota", ", ND", .)
replace county_name = subinstr(county_name, ", Ohio", ", OH", .)
replace county_name = subinstr(county_name, ", Oklahoma", ", OK", .)
replace county_name = subinstr(county_name, ", Oregon", ", OR", .)
replace county_name = subinstr(county_name, ", Pennsylvania", ", PA", .)
replace county_name = subinstr(county_name, ", Rhode Island", ", RI", .)
replace county_name = subinstr(county_name, ", South Carolina", ", SC", .)
replace county_name = subinstr(county_name, ", South Dakota", ", SD", .)
replace county_name = subinstr(county_name, ", Tennessee", ", TN", .)
replace county_name = subinstr(county_name, ", Texas", ", TX", .)
replace county_name = subinstr(county_name, ", Utah", ", UT", .)
replace county_name = subinstr(county_name, ", Vermont", ", VT", .)
replace county_name = subinstr(county_name, ", Virginia", ", VA", .)
replace county_name = subinstr(county_name, ", Washington", ", WA", .)
replace county_name = subinstr(county_name, ", West Virginia", ", WV", .)
replace county_name = subinstr(county_name, ", Wisconsin", ", WI", .)
replace county_name = subinstr(county_name, ", Wyoming", ", WY", .)

save "`savedir'/county_all_vars_wide.dta", replace

keep countyid county_name state qpop qpotential

** save more variables for post-index
merge 1:m countyid using "`stardir'/90_22_long.dta", nogen
merge 1:1 countyid year using "`stardir'/income/90_22_long.dta", nogen
merge 1:1 countyid year using  "`maindir'/mfgsh_long.dta", nogen

*drop unnecessary variables
drop incss_recipients incss_recipients_STARS incss_recipients_lf incss_recipients_nonlf incss_recipients_STARS_lf incss_recipients_STARS_nonlf incss_sum incss_sum_STARS incss_med incss_med_STARS incss_avg incss_avg_STARS incss_nat_avg incss_nat_med incss_nat_avg_STARS incss_nat_med_STARS STAR_emp_rate pcttotalworkerscounty pcttotalstars pctemployedworkers pctemployedstars pctcountymedian pctstarmedian pctemploymentrate pctstaremprate

* Make sure data is sorted
sort countyid year

* For each county, replace 1990 values with 1991 values of mfgsh, totemp, mfgemp
bysort countyid (year): replace mfgsh = mfgsh[_n+1] if year==1990 & year[_n+1]==1991
bysort countyid (year): replace mfgemp = mfgemp[_n+1] if year==1990 & year[_n+1]==1991

* Linear interpolation between known years (1990, 2000, 2011)
bys countyid: ipolate mfgsh year, gen(mfgsh_lin)
bys countyid: ipolate mfgemp year, gen(mfgemp_lin)

replace mfgsh = mfgsh_lin if mfgsh == .
replace mfgemp = mfgemp_lin if mfgemp == . 

drop mfgsh_lin mfgemp_lin

* Drop the 1991 rows
drop if year==1991

gen star_share = totalstars/totalworkers

gen pct_star_midupp = pct_star_upper + pct_star_middle
gen pct_total_middupp = pct_total_upper + pct_total_middle
gen pct_college_middupp = pct_college_upper + pct_college_middle

* generate weighted average star employment rates by population quintile
egen qpop_pop_total = sum(totalstars), by(qpop year)
gen qpop_emp_rate_wgt = totalstars* staremprate
egen qpop_star_emp_total = sum(qpop_emp_rate_wgt), by(qpop year)
gen star_emp_rate_qpop_avg = qpop_star_emp_total/qpop_pop_total
gen star_unemp_rate_qpop_avg = 100*(1 - star_emp_rate_qpop_avg)
gen name_short = word(county_name, 1)+" Co, " + word(county_name,-1)


sort countyid year
order countyid county_name year
save "`savedir'/county_all_vars_long.dta", replace
export delimited "`savedir'/county_all_vars_long.csv", replace
