/* -------------  Rules from the statutes that are relevant to this case ------------- */

/* route involved - from U.S. to Europe (Charlotte -> Barcelona) */
route(us_europe).

/* cabin class */
cabin(first_class).

/* ---------------- Checked-bag fees by bag number for First Class passengers
      on a U.S. <-> Europe itinerary                                ------------- */
bag_number_fee(Num, 0) :- Num =< 3.         /* 1st - 3rd bag free                */
bag_number_fee(Num, 200) :- Num  >= 4.      /* 4th bag and higher = $200 each     */

/* ---------------- Oversize fees (U.S. <-> Europe) ----------------
   Size = L+W+H in inches                                                     */
oversize_fee(Size, 0)    :- Size =< 62.                     /* within limit     */
oversize_fee(Size, 30)   :- Size > 62, Size =< 65.          /* 62-65 in         */
oversize_fee(Size, 150)  :- Size > 65, Size =< 115.         /* 65-115 in        */

/* ---------------- Over-weight fees -----------------------------------------
   Only the brackets that can possibly occur in this case are encoded.        */
overweight_fee(Weight, 0)  :- Weight =< 50.                 /* within limit     */
overweight_fee(Weight, 30) :- Weight  > 50, Weight =< 53.   /* 50-53 lb         */
overweight_fee(Weight, 100) :- Weight > 53, Weight =< 70.   /* 53-70 lb         */

/* ------------- When both oversize and overweight apply --------------------
   Pay the higher of the two, in addition to any bag-number fee               */
bag_extra_fee(Size, Weight, Fee) :-
    oversize_fee(Size, OSFee),
    overweight_fee(Weight, OWFee),
    ( OSFee >= OWFee -> Fee = OSFee ; Fee = OWFee ).

/* ------------- Cost of an individual checked bag -------------------------- */
bag_cost(Num, Size, Weight, Cost) :-
    bag_number_fee(Num, NumFee),
    bag_extra_fee(Size, Weight, ExtraFee),
    Cost is NumFee + ExtraFee.

/* ---------------------------  Facts for this case -------------------------- */

/* Flight ticket price */
flight_ticket(637).

/* Carry-on backpack - free, so not listed as a checked bag */

/*                               Num, Size-Sum, Weight */
checked_bag(1, 64, 51).
checked_bag(2, 65, 52).
checked_bag(3, 65, 52).
checked_bag(4, 64, 52).

/* -----------------------  Aggregate bag fees -------------------------------- */
total_checked_bags_cost(Total) :-
    findall(C,
            (checked_bag(Num,Size,Weight),
             bag_cost(Num,Size,Weight,C)),
            Costs),
    sum_list(Costs, Total).

/* -----------------------  Grand total --------------------------------------- */
total_cost(Total) :-
    flight_ticket(Ticket),
    total_checked_bags_cost(BagFees),
    Total is Ticket + BagFees.

/* -----------------------  Query & print answer ------------------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.