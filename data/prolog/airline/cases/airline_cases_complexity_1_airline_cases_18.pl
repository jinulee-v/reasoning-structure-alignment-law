/* ----------  Statutory rules that are relevant to this case ---------- */

/* checked_bag_fee(+BagNumber,+Itinerary,+Class,-Fee)                  */
/* Only the rules that apply to flights FROM Cuba TO the U.S.          */
checked_bag_fee(1,cuba_to_us,premium_economy,0).   /* 1st bag */
checked_bag_fee(2,cuba_to_us,premium_economy,0).   /* 2nd bag */

/* overweight_fee(+Weight,+Itinerary,+Class,-Fee)                      */
/* We only need the ">50-53lbs" bracket ($30) for any itinerary / class*/
overweight_fee(Weight,_,_,30) :- Weight>50, Weight=<53.

/* oversize_fee(+SizeSum,+Itinerary,-Fee)                              */
/* Cuba->U.S. is treated as "to / from Caribbean" -> 62-65in costs $30   */
oversize_fee(Size,cuba_to_us,30)  :- Size>62, Size=<65.

/* extra_fee(+Weight,+SizeSum,+Itinerary,+Class,-Fee)                  */
/* The higher of overweight vs. oversize (0 if neither applies)        */
extra_fee(W,S,Itin,Class,Fee) :-
    (overweight_fee(W,Itin,Class,OWF) -> true ; OWF=0),
    (oversize_fee(S,Itin,OSF)        -> true ; OSF=0),
    Fee is max(OWF,OSF).

/* bag_cost(+BagNumber,+Weight,+SizeSum,+Itinerary,+Class,-Cost)       */
bag_cost(N,W,S,Itin,Class,Cost) :-
    checked_bag_fee(N,Itin,Class,CheckedFee),
    extra_fee(W,S,Itin,Class,Extra),
    Cost is CheckedFee+Extra.

/* ----------  Facts for Emily's trip --------------------------------- */

ticket_price(163).

itinerary(cuba_to_us).
passenger_class(premium_economy).

/* Two checked bags (carry-on backpack is free and therefore omitted)  */
bag(1,53,64).      /* Bag 1: 53 lbs, 64 in (L+W+H) */
bag(2,51,65).      /* Bag 2: 51 lbs, 65 in (L+W+H) */

/* ----------  Total cost calculation --------------------------------- */

total_bags_cost(Total) :-
    itinerary(Itin),
    passenger_class(Class),
    findall(C,
            (bag(N,W,S), bag_cost(N,W,S,Itin,Class,C)),
            Costs),
    sum_list(Costs,Total).

total_cost(Total) :-
    ticket_price(Tix),
    total_bags_cost(Bags),
    Total is Tix+Bags.

/* ----------  Query --------------------------------------------------- */

:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.