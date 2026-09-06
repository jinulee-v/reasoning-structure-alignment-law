/* ---------------  Statutory rules that apply to this case --------------- */

/*  Base checked-bag fees for a Main Cabin passenger on itineraries
    to / from Australia-New Zealand (amounts in U.S. dollars)           */
base_checked_bag_fee(1,0).          /* 1st bag - complimentary          */
base_checked_bag_fee(2,100).        /* 2nd bag                          */
base_checked_bag_fee(N,200) :-      /* 3rd bag and every bag thereafter */
    N >= 3.

/*  Oversize fees (to / from Australia-New Zealand)                     */
oversize_fee(Size,30)  :- Size  > 62, Size =< 65.      /* 62-65 in  */
oversize_fee(Size,200) :- Size  > 65, Size =< 115.     /* 65-115 in */
oversize_fee(Size,0)   :- Size =< 62.                  /* within limit */

/*  Over-weight fees (to / from Australia-New Zealand)                  */
overweight_fee(Weight,30)  :- Weight > 50, Weight =< 53.
overweight_fee(Weight,100) :- Weight > 53, Weight =< 70.
overweight_fee(Weight,0)   :- Weight =< 50.

/*  For bags that are both oversize and overweight, only the
    higher of the two surcharges is collected.                          */
extra_fee(Weight,Size,Fee) :-
    overweight_fee(Weight,WFee),
    oversize_fee(Size,SFee),
    (   WFee >= SFee -> Fee = WFee
    ;   Fee = SFee).

/* ---------------  Facts for Michael's journey --------------- */

/*  Flight ticket price                                                  */
flight_ticket_price(800).

/*  Checked bags (index, length, width, height, weight in pounds)        */
bag(1,46,22,19,51).
bag(2,50,30,25,54).
bag(3,33,20,11,52).
bag(4,40,15,17,51).
bag(5,45,32,24,52).
bag(6,34,16,14,51).
bag(7,52,31,30,53).

/*  Helper: compute total outside dimension of a bag                     */
bag_size(Index,Size) :-
    bag(Index,L,W,H,_),
    Size is L + W + H.

/*  Helper: compute cost of an individual bag                            */
bag_cost(Index,Cost) :-
    bag(Index,_,_,_,Weight),
    bag_size(Index,Size),
    base_checked_bag_fee(Index,BaseFee),
    extra_fee(Weight,Size,ExtraFee),
    Cost is BaseFee + ExtraFee.

/*  Sum of all checked-bag costs                                         */
total_bag_fees(Total) :-
    findall(C,bag_cost(_,C),Cs),
    sum_list(Cs,Total).

/*  Overall cost (ticket + all bag fees)                                 */
total_cost(Total) :-
    flight_ticket_price(Ticket),
    total_bag_fees(BagFees),
    Total is Ticket + BagFees.

/* ---------------  Query to display the answer --------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.